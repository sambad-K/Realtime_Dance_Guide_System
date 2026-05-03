let pendingPracticeTransfer = null;

export function setPracticeTransfer(payload) {
  pendingPracticeTransfer = payload;
}

export function consumePracticeTransfer() {
  const next = pendingPracticeTransfer;
  pendingPracticeTransfer = null;
  return next;
}
