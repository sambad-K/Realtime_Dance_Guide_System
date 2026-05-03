# services/stgcn_model_def.py
import torch
import torch.nn as nn


class GraphConv(nn.Module):
    def __init__(self, Cin: int, Cout: int):
        super().__init__()
        self.conv = nn.Conv2d(Cin, Cout, kernel_size=1, bias=False)
        self.bn = nn.BatchNorm2d(Cout)

    def forward(self, x, A):
        # x: (B,C,T,V), A: (V,V)
        x = torch.einsum("bctv,vw->bctw", x, A)
        x = self.conv(x)
        x = self.bn(x)
        return x


class STGCNBlock(nn.Module):
    """
    IMPORTANT: Matches your checkpoint naming:
      - blocks.i.tcn.weight  (single Conv2d)
      - blocks.i.bn.*        (BatchNorm2d at block level)
    """
    def __init__(self, Cin: int, Cout: int, stride: int = 1):
        super().__init__()
        self.gcn = GraphConv(Cin, Cout)

        self.tcn = nn.Conv2d(
            Cout, Cout,
            kernel_size=(9, 1),
            padding=(4, 0),
            stride=(stride, 1),
            bias=False
        )
        self.bn = nn.BatchNorm2d(Cout)

        if Cin == Cout and stride == 1:
            self.res = nn.Identity()
        else:
            self.res = nn.Sequential(
                nn.Conv2d(Cin, Cout, kernel_size=1, stride=(stride, 1), bias=False),
                nn.BatchNorm2d(Cout),
            )

        self.act = nn.ReLU(inplace=False)

    def forward(self, x, A):
        r = self.res(x)
        x = self.gcn(x, A)
        x = self.tcn(x)
        x = self.bn(x)
        return self.act(x + r)


class STGCNEncoder(nn.Module):
    """
    Output embedding dim = 256 (fixed by your checkpoint).
    Final head matches checkpoint:
      fc.0 = Linear(256->256)
      fc.1 = BatchNorm1d(256)
    """
    def __init__(self, A: torch.Tensor, in_channels: int = 2, V: int = 17):
        super().__init__()
        self.register_buffer("A", A)

        self.blocks = nn.ModuleList([
            STGCNBlock(in_channels, 64, stride=1),
            STGCNBlock(64, 128, stride=2),
            STGCNBlock(128, 256, stride=2),
        ])

        self.pool = nn.AdaptiveAvgPool2d((1, 1))

        # ✅ EXACT match for your checkpoint keys/shapes
        self.fc = nn.Sequential(
            nn.Linear(256, 256, bias=True),
            nn.LayerNorm(256),
        )


    def forward(self, x):
        """
        x: (B,2,T,V,1) or (B,2,T,V)
        returns: (B,256)
        """
        if x.dim() == 5:
            x = x.squeeze(-1)  # (B,2,T,V)

        for b in self.blocks:
            x = b(x, self.A)

        x = self.pool(x).flatten(1)  # (B,256)
        z = self.fc(x)               # (B,256)
        return z


class STGCNAutoEncoder(nn.Module):
    """
    Decoder not needed for embedding in backend, but wrapper keeps `.encoder`.
    """
    def __init__(self, A: torch.Tensor, in_channels: int = 2, V: int = 17):
        super().__init__()
        self.encoder = STGCNEncoder(A, in_channels=in_channels, V=V)
        self.decoder = nn.Identity()

    def forward(self, x):
        return self.encoder(x)


def build_model(A: torch.Tensor, in_channels: int = 2, latent_dim: int = 256, V: int = 17, dropout: float = 0.0):
    """
    Factory used by stgcn_embed.py.
    latent_dim/dropout are ignored because your saved encoder head is fixed to 256.
    """
    return STGCNAutoEncoder(A, in_channels=in_channels, V=V)
