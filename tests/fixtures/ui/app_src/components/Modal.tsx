export function Modal({ open, children }) { return open ? <div role="dialog">{children}</div> : null; }
