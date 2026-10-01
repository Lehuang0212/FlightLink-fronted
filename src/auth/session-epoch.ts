let sessionEpoch = 0

export function currentSessionEpoch(): number {
  return sessionEpoch
}

export function advanceSessionEpoch(): number {
  sessionEpoch += 1
  return sessionEpoch
}
