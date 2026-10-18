/**
 * A minimal DOM for container-level analytics tests.
 *
 * WHY THIS EXISTS
 *
 * `AnalyticsView` is pure, so the existing tests render it with `react-dom/server`: props
 * in, markup out, no effects. That cannot cover the defects this dashboard actually had,
 * because all four live in effects and interaction (a grouping change while a request is
 * in flight, a stale pagination cursor, a caption taken from the wrong selection, an
 * invalid period leaving stale figures on screen).
 *
 * Covering them needs a mounted component, which means a DOM. This workspace has no
 * `jsdom`, no `happy-dom`, no `@testing-library/react` and no `react-test-renderer`
 * installed, and the analytics work is not allowed to add dependencies. Node's own
 * environment provides none of the DOM either, so the small surface `react-dom/client`
 * actually touches is implemented here, in ~400 lines, and nothing else.
 *
 * WHAT IT IMPLEMENTS
 *
 * - Node tree: createElement/createTextNode/createComment/createDocumentFragment,
 *   appendChild/insertBefore/removeChild/replaceChild, childNodes/firstChild/lastChild/
 *   parentNode/nextSibling, contains, textContent/nodeValue/data.
 * - The properties `react-dom` reads or writes on host elements: `style` (with
 *   `setProperty`), attributes, `value`/`checked`/`selected`/`disabled`/`multiple`/`name`/
 *   `type`/`defaultValue`/`defaultChecked`, and `options` on a `<select>`.
 * - A bubbling event path with capture and bubble phases, so a synthetic
 *   `click`/`change`/`input` dispatched at a nested element reaches the listener
 *   `react-dom` registered on the root container.
 * - The handful of globals `react-dom` probes at import time (`window`, `document`,
 *   `Element`, `Node`, `navigator`, `MessageChannel`), including the `'oninput' in
 *   document` feature test that decides whether the native `input` event may be used for
 *   `onChange`. `react-dom` computes `canUseDOM` once, at import, so {@link installDom}
 *   MUST run before `react-dom/client` is imported - see the container test for how the
 *   import order is enforced.
 *
 * WHAT IT DELIBERATELY DOES NOT DO
 *
 * No layout, no CSS cascade, no `innerHTML` parsing, no focus/selection model, no
 * `querySelector`. Nothing here is a substitute for a browser: it exists so effect-driven
 * behaviour can be exercised in-process, and assertions are written against the DOM tree
 * this shim builds, not against rendered geometry.
 */

export const ELEMENT_NODE = 1;
export const TEXT_NODE = 3;
export const COMMENT_NODE = 8;
export const DOCUMENT_NODE = 9;
export const DOCUMENT_FRAGMENT_NODE = 11;

export interface ShimStyle {
  setProperty(name: string, value: string): void;
  removeProperty(name: string): void;
  getPropertyValue(name: string): string;
  cssText: string;
  [name: string]: unknown;
}

/**
 * An event with the shape `react-dom`'s synthetic event layer reads.
 *
 * `react-dom` copies fields off the native event through its own interface list and only
 * requires `type`, `target` and `defaultPrevented`; the rest are optional extras.
 */
export class ShimEvent {
  type: string;
  target: ShimNode | null = null;
  srcElement: ShimNode | null = null;
  currentTarget: ShimNode | null = null;
  bubbles: boolean;
  cancelable: boolean;
  composed = true;
  defaultPrevented = false;
  eventPhase = 0;
  isTrusted = true;
  timeStamp: number;
  returnValue = true;
  stopPropagation = (): void => {
    this.propagationMarker = true;
  };
  stopImmediatePropagation = (): void => {
    this.propagationMarker = true;
    this.immediateMarker = true;
  };
  private propagationMarker = false;
  private immediateMarker = false;

  /** Read by the event path: propagation was stopped for the rest of the tree. */
  get propagationWasStopped(): boolean {
    return this.propagationMarker;
  }

  /** Read by the event path: no further listener may run at all. */
  get immediatePropagationWasStopped(): boolean {
    return this.immediateMarker;
  }

  constructor(type: string, init: { bubbles?: boolean; cancelable?: boolean } = {}) {
    this.type = type;
    this.bubbles = init.bubbles ?? false;
    this.cancelable = init.cancelable ?? false;
    this.timeStamp = Date.now();
  }

  preventDefault(): void {
    this.defaultPrevented = true;
    this.returnValue = false;
  }
}

type Listener = (event: ShimEvent) => void;

/** The node/event/attribute surface shared by every node kind. */
export class ShimNode {
  readonly nodeType: number;
  readonly nodeName: string;
  readonly childNodes: ShimNode[] = [];
  parentNode: ShimNode | null = null;
  ownerDocument: ShimDocument | null = null;

  private readonly listeners = new Map<string, Listener[]>();
  private nodeData = "";

  constructor(nodeType: number, nodeName: string) {
    this.nodeType = nodeType;
    this.nodeName = nodeName;
  }

  get firstChild(): ShimNode | null {
    return this.childNodes[0] ?? null;
  }

  get lastChild(): ShimNode | null {
    return this.childNodes[this.childNodes.length - 1] ?? null;
  }

  get nextSibling(): ShimNode | null {
    const parent = this.parentNode;
    if (!parent) return null;
    const index = parent.childNodes.indexOf(this);
    if (index < 0) return null;
    return parent.childNodes[index + 1] ?? null;
  }

  get previousSibling(): ShimNode | null {
    const parent = this.parentNode;
    if (!parent) return null;
    const index = parent.childNodes.indexOf(this);
    return index > 0 ? (parent.childNodes[index - 1] ?? null) : null;
  }

  get parentElement(): ShimNode | null {
    return this.parentNode;
  }

  /**
   * `data` and `nodeValue` are the same backing field on purpose: `react-dom` updates a
   * text node through `nodeValue` and reads it back through `firstChild.nodeValue`, while
   * the assertions in these tests read `textContent`. Keeping them separate silently
   * freezes rendered text at its first value.
   */
  get data(): string {
    return this.nodeData;
  }

  set data(value: string) {
    this.nodeData = String(value);
  }

  get nodeValue(): string | null {
    return this.nodeType === ELEMENT_NODE ? null : this.nodeData;
  }

  set nodeValue(value: string | null) {
    if (this.nodeType === ELEMENT_NODE) return;
    this.nodeData = value === null ? "" : String(value);
  }

  get textContent(): string {
    if (this.nodeType === TEXT_NODE || this.nodeType === COMMENT_NODE) return this.nodeData;
    let out = "";
    for (const child of this.childNodes) out += child.textContent;
    return out;
  }

  set textContent(value: string | null) {
    const text = value === null ? "" : String(value);
    this.childNodes.length = 0;
    if (text === "") return;
    const document = this.ownerDocument;
    if (!document) return;
    const node = document.createTextNode(text);
    node.parentNode = this;
    this.childNodes.push(node);
  }

  private adopt(child: ShimNode): void {
    if (child.parentNode) child.parentNode.removeChild(child);
    child.parentNode = this;
    if (!child.ownerDocument && this.ownerDocument) child.ownerDocument = this.ownerDocument;
  }

  appendChild<T extends ShimNode>(child: T): T {
    this.adopt(child);
    this.childNodes.push(child);
    return child;
  }

  insertBefore<T extends ShimNode>(child: T, reference: ShimNode | null): T {
    if (!reference) return this.appendChild(child);
    const index = this.childNodes.indexOf(reference);
    if (index < 0) throw new Error("insertBefore: the reference node is not a child");
    this.adopt(child);
    this.childNodes.splice(index, 0, child);
    return child;
  }

  removeChild<T extends ShimNode>(child: T): T {
    const index = this.childNodes.indexOf(child);
    if (index < 0) throw new Error("removeChild: the node is not a child");
    this.childNodes.splice(index, 1);
    child.parentNode = null;
    return child;
  }

  replaceChild<T extends ShimNode>(newChild: T, oldChild: ShimNode): T {
    const index = this.childNodes.indexOf(oldChild);
    if (index < 0) throw new Error("replaceChild: the node is not a child");
    this.adopt(newChild);
    this.childNodes.splice(index, 1, newChild);
    oldChild.parentNode = null;
    return newChild;
  }

  hasChildNodes(): boolean {
    return this.childNodes.length > 0;
  }

  contains(other: ShimNode | null): boolean {
    for (let node = other; node; node = node.parentNode) {
      if (node === this) return true;
    }
    return false;
  }

  // --- events -------------------------------------------------------------

  addEventListener(type: string, listener: Listener, options?: boolean | { capture?: boolean }): void {
    if (!listener) return;
    const key = listenerKey(type, options);
    const existing = this.listeners.get(key);
    if (existing) {
      if (!existing.includes(listener)) existing.push(listener);
      return;
    }
    this.listeners.set(key, [listener]);
  }

  removeEventListener(
    type: string,
    listener: Listener,
    options?: boolean | { capture?: boolean },
  ): void {
    const existing = this.listeners.get(listenerKey(type, options));
    if (!existing) return;
    const index = existing.indexOf(listener);
    if (index >= 0) existing.splice(index, 1);
  }

  /** Listeners registered for one phase of one event type. */
  listenersFor(type: string, capture: boolean): readonly Listener[] {
    return this.listeners.get(`${type}|${capture ? 1 : 0}`) ?? [];
  }

  /**
   * Run an event through the capture phase (root to target) then the bubble phase (target
   * to root). `react-dom` registers one delegated listener per event type on the root
   * container, so a bubbling event dispatched on a nested element has to walk up to it.
   */
  dispatchEvent(event: ShimEvent): boolean {
    if (!event || typeof event.type !== "string") {
      throw new TypeError("dispatchEvent: expected an Event");
    }
    if (!event.target) {
      event.target = this;
      event.srcElement = this;
    }

    const path = this.ancestorChain();

    let stopped = false;
    for (let index = path.length - 1; index >= 0; index -= 1) {
      const node = path[index];
      if (!node) continue;
      if (!this.invoke(node, event, true)) {
        stopped = true;
        break;
      }
    }
    if (!stopped) {
      for (const node of path) {
        if (!this.invoke(node, event, false)) break;
      }
    }
    event.currentTarget = null;
    return !event.defaultPrevented;
  }

  /** Returns false when propagation must stop. */
  private invoke(node: ShimNode, event: ShimEvent, capture: boolean): boolean {
    for (const listener of node.listenersFor(event.type, capture)) {
      event.currentTarget = node;
      event.eventPhase = node === this ? 2 : capture ? 1 : 3;
      listener.call(node, event);
      if (event.immediatePropagationWasStopped) return false;
    }
    return !event.propagationWasStopped;
  }

  /** This node first, then each ancestor: the path an event travels. */
  private ancestorChain(): ShimNode[] {
    const chain: ShimNode[] = [this];
    let parent = this.parentNode;
    while (parent) {
      chain.push(parent);
      parent = parent.parentNode;
    }
    return chain;
  }
}

/** Key for one event type in one phase. */
function listenerKey(type: string, options?: boolean | { capture?: boolean }): string {
  const capture = typeof options === "boolean" ? options : Boolean(options?.capture);
  return `${type}|${capture ? 1 : 0}`;
}

function createStyle(): ShimStyle {
  const style: ShimStyle = {
    setProperty(name: string, value: string) {
      style[name] = value;
    },
    removeProperty(name: string) {
      delete style[name];
    },
    getPropertyValue(name: string) {
      const value = style[name];
      return typeof value === "string" ? value : "";
    },
    cssText: "",
  };
  return style;
}

export class ShimElement extends ShimNode {
  readonly tagName: string;
  readonly localName: string;
  readonly style: ShimStyle = createStyle();
  namespaceURI = "http://www.w3.org/1999/xhtml";
  innerHTML = "";
  checked = false;
  defaultChecked = false;
  defaultValue = "";
  disabled = false;
  multiple = false;
  name = "";
  type = "";

  private readonly attributes = new Map<string, string>();
  private currentValue = "";
  private isSelected = false;

  constructor(tagName: string, ownerDocument: ShimDocument | null) {
    super(ELEMENT_NODE, tagName.toUpperCase());
    this.tagName = tagName;
    this.localName = tagName.toLowerCase();
    this.ownerDocument = ownerDocument;
  }

  /**
   * The value, exactly as a browser exposes it: a prototype accessor, not an own data
   * property. That matters. `react-dom` installs its *own* `value` setter over an input
   * that does not already own the property, uses it to remember what it last wrote, and
   * treats a differing `node.value` as "the user changed this". Assigning through that
   * setter therefore looks like React's own write and fires no `onChange` at all; see
   * {@link ShimElement.setNativeValue}, which is how these tests simulate a keystroke.
   */
  get value(): string {
    return this.currentValue;
  }

  set value(next: string) {
    this.currentValue = String(next ?? "");
  }

  /**
   * Change the value behind the property setter, the way a user's keystroke does.
   *
   * This is the same trick DOM testing libraries use to drive a controlled input: the
   * native setter moves the real value while `react-dom`'s tracker keeps the previous one,
   * which is the difference `onChange` is dispatched for.
   */
  setNativeValue(next: string): void {
    this.currentValue = String(next ?? "");
  }

  get selected(): boolean {
    return this.isSelected;
  }

  set selected(next: boolean) {
    this.isSelected = Boolean(next);
  }

  setAttribute(name: string, value: string): void {
    const key = String(name);
    this.attributes.set(key, String(value));
    if (key === "value") this.value = String(value);
    if (key === "type") this.type = String(value);
  }

  getAttribute(name: string): string | null {
    return this.attributes.get(String(name)) ?? null;
  }

  /**
   * Present so a failing assertion can print an element: chai's inspector detects a DOM
   * node and lists its attributes through this method.
   */
  getAttributeNames(): string[] {
    return [...this.attributes.keys()];
  }

  hasAttribute(name: string): boolean {
    return this.attributes.has(String(name));
  }

  removeAttribute(name: string): void {
    this.attributes.delete(String(name));
  }

  get className(): string {
    return this.attributes.get("class") ?? "";
  }

  set className(next: string) {
    this.attributes.set("class", String(next));
  }

  get children(): ShimElement[] {
    return this.childNodes.filter((node): node is ShimElement => node instanceof ShimElement);
  }

  /** What `react-dom` walks when it syncs a controlled `<select>` to its options. */
  get options(): ShimElement[] {
    return this.children.filter((node) => node.localName === "option");
  }

  get selectedOptions(): ShimElement[] {
    return this.options.filter((option) => option.selected);
  }

  get firstElementChild(): ShimElement | null {
    return this.children[0] ?? null;
  }

  focus(): void {
    if (this.ownerDocument) this.ownerDocument.activeElement = this;
  }

  blur(): void {
    if (this.ownerDocument) this.ownerDocument.activeElement = this.ownerDocument.body;
  }

  click(): void {
    this.dispatchEvent(new ShimEvent("click", { bubbles: true, cancelable: true }));
  }
}

export class ShimDocument extends ShimNode {
  readonly documentElement: ShimElement;
  readonly body: ShimElement;
  readonly head: ShimElement;
  activeElement: ShimElement;
  documentMode: number | undefined = undefined;
  defaultView: ShimWindow | null = null;

  /**
   * Real documents expose the handler content attributes, and `react-dom` asks
   * `'oninput' in document` once at import to decide whether it may rely on the native
   * `input` event for `onChange`. Without this the change plugin falls back to its legacy
   * keyup/selectionchange polyfill and a synthetic `input` event never reaches `onChange`.
   */
  oninput: null = null;

  constructor() {
    super(DOCUMENT_NODE, "#document");
    this.ownerDocument = this;
    this.documentElement = new ShimElement("html", this);
    this.head = new ShimElement("head", this);
    this.body = new ShimElement("body", this);
    this.documentElement.appendChild(this.head);
    this.documentElement.appendChild(this.body);
    this.appendChild(this.documentElement);
    this.activeElement = this.body;
  }

  createElement(tagName: string): ShimElement {
    return new ShimElement(tagName, this);
  }

  createElementNS(_namespace: string, tagName: string): ShimElement {
    return new ShimElement(tagName, this);
  }

  createTextNode(data: string): ShimNode {
    const node = new ShimNode(TEXT_NODE, "#text");
    node.ownerDocument = this;
    node.data = data;
    return node;
  }

  createComment(data: string): ShimNode {
    const node = new ShimNode(COMMENT_NODE, "#comment");
    node.ownerDocument = this;
    node.data = data;
    return node;
  }

  createDocumentFragment(): ShimNode {
    const node = new ShimNode(DOCUMENT_FRAGMENT_NODE, "#document-fragment");
    node.ownerDocument = this;
    return node;
  }
}

export interface ShimWindow {
  document: ShimDocument;
  setTimeout: (...args: unknown[]) => unknown;
  clearTimeout: (handle: unknown) => void;
  setInterval: (...args: unknown[]) => unknown;
  clearInterval: (handle: unknown) => void;
  requestAnimationFrame: (callback: (time: number) => void) => unknown;
  cancelAnimationFrame: (handle: unknown) => void;
  addEventListener: () => void;
  removeEventListener: () => void;
  dispatchEvent: () => boolean;
  navigator: { userAgent: string };
  performance: Performance;
  getComputedStyle: () => null;
  location: { href: string; protocol: string; reload: () => void };
  event: undefined;
  Node: typeof ShimNode;
  Element: typeof ShimElement;
  HTMLElement: typeof ShimElement;
  HTMLIFrameElement: typeof ShimElement;
  HTMLInputElement: typeof ShimElement;
  HTMLSelectElement: typeof ShimElement;
  HTMLTextAreaElement: typeof ShimElement;
  HTMLButtonElement: typeof ShimElement;
  [key: string]: unknown;
}

export interface ShimDom {
  document: ShimDocument;
  window: ShimWindow;
}

/**
 * Install the shim as the process globals and return it.
 *
 * Must be called before `react-dom/client` is first imported: `react-dom` evaluates
 * `canUseDOM` and its input-event support probe at module scope, and a `react-dom` loaded
 * against an empty global object never attaches its delegated listeners or uses the native
 * `input` event.
 */
export function installDom(): ShimDom {
  const document = new ShimDocument();
  const window: ShimWindow = {
    document,
    setTimeout: (...args) => globalThis.setTimeout(...(args as [() => void, number?])),
    clearTimeout: (handle) => globalThis.clearTimeout(handle as ReturnType<typeof globalThis.setTimeout>),
    setInterval: (...args) => globalThis.setInterval(...(args as [() => void, number?])),
    clearInterval: (handle) => globalThis.clearInterval(handle as ReturnType<typeof globalThis.setInterval>),
    requestAnimationFrame: (callback) => globalThis.setTimeout(() => callback(Date.now()), 16),
    cancelAnimationFrame: (handle) => globalThis.clearTimeout(handle as ReturnType<typeof globalThis.setTimeout>),
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => true,
    navigator: { userAgent: "proofline-console-test-dom" },
    performance: globalThis.performance,
    getComputedStyle: () => null,
    location: { href: "http://localhost:3001/", protocol: "http:", reload: () => {} },
    event: undefined,
    Node: ShimNode,
    Element: ShimElement,
    HTMLElement: ShimElement,
    HTMLIFrameElement: ShimElement,
    HTMLInputElement: ShimElement,
    HTMLSelectElement: ShimElement,
    HTMLTextAreaElement: ShimElement,
    HTMLButtonElement: ShimElement,
  };
  document.defaultView = window;

  const globals = globalThis as unknown as Record<string, unknown>;
  globals.document = document;
  globals.window = window;
  globals.Node = ShimNode;
  globals.Element = ShimElement;
  globals.HTMLElement = ShimElement;
  globals.Event = ShimEvent;
  globals.CustomEvent = ShimEvent;
  globals.MouseEvent = ShimEvent;
  Object.defineProperty(globalThis, "navigator", {
    value: window.navigator,
    configurable: true,
    writable: true,
  });
  // Tells React an act() environment is in effect, so effects are flushed with the test
  // and updates outside `act` are reported instead of silently deferred.
  globals.IS_REACT_ACT_ENVIRONMENT = true;

  return { document, window };
}

// ---------------------------------------------------------------------------
// Query and interaction helpers (deliberately small: no CSS selectors)
// ---------------------------------------------------------------------------

export function findAll(
  root: ShimNode,
  predicate: (element: ShimElement) => boolean,
  found: ShimElement[] = [],
): ShimElement[] {
  if (root instanceof ShimElement && predicate(root)) found.push(root);
  for (const child of root.childNodes) findAll(child, predicate, found);
  return found;
}

export function textOf(root: ShimNode): string {
  return root.textContent;
}

export function findButton(root: ShimNode, label: string): ShimElement {
  const match = findAll(
    root,
    (element) => element.localName === "button" && element.textContent.trim() === label,
  )[0];
  if (!match) throw new Error(`no button labelled "${label}" was rendered`);
  return match;
}

export function findLabelled(root: ShimNode, label: string): ShimElement {
  const match = findAll(root, (element) => element.getAttribute("aria-label") === label)[0];
  if (!match) throw new Error(`no control labelled "${label}" was rendered`);
  return match;
}

export function click(element: ShimElement): void {
  element.dispatchEvent(new ShimEvent("click", { bubbles: true, cancelable: true }));
}

/** Set a `<select>`'s value the way a user would, then report the change. */
export function chooseOption(select: ShimElement, value: string): void {
  select.setNativeValue(value);
  select.dispatchEvent(new ShimEvent("change", { bubbles: true }));
}

/** Type into a text/date input the way a user would, then report the input. */
export function setInputValue(input: ShimElement, value: string): void {
  input.setNativeValue(value);
  input.dispatchEvent(new ShimEvent("input", { bubbles: true }));
}
