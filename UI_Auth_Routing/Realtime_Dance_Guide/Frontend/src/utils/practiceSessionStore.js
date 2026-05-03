let practiceSession = null;

export function getPracticeSession() {
  return practiceSession;
}

export function setPracticeSession(nextSession) {
  practiceSession = nextSession;
}

export function clearPracticeSession() {
  practiceSession = null;
}
