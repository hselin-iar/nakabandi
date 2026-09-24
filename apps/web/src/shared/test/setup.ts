/**
 * setup.ts — vitest global test setup.
 *
 * jsdom does not implement pointer capture or scrollIntoView, which @radix-ui/react-select
 * and @radix-ui/react-tooltip call unconditionally when opening — without these stubs every
 * test that opens a Select or Tooltip throws "not a function" inside jsdom.
 */

if (!Element.prototype.hasPointerCapture) {
  Element.prototype.hasPointerCapture = () => false;
}
if (!Element.prototype.setPointerCapture) {
  Element.prototype.setPointerCapture = () => {};
}
if (!Element.prototype.releasePointerCapture) {
  Element.prototype.releasePointerCapture = () => {};
}
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}
