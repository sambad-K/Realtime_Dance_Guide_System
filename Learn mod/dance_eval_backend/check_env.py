import os
from config import Config

print('ENV_KEY_SET:', bool(os.getenv('OPENROUTER_API_KEY')))
print('Config.STGCN_CKPT:', Config.STGCN_CKPT)
