import '@testing-library/jest-dom';
import { toHaveNoViolations } from 'jest-axe';
expect.extend(toHaveNoViolations);

if (typeof window !== 'undefined') {
  class StorageMock {
    constructor() {
      this.store = new Map();
    }
    get length() {
      return this.store.size;
    }
    key(index) {
      return Array.from(this.store.keys())[index] ?? null;
    }
    getItem(key) {
      return this.store.has(String(key)) ? this.store.get(String(key)) : null;
    }
    setItem(key, value) {
      this.store.set(String(key), String(value));
    }
    removeItem(key) {
      this.store.delete(String(key));
    }
    clear() {
      this.store.clear();
    }
  }

  // If window.Storage is missing or inoperative, install StorageMock
  if (!window.Storage || !window.localStorage) {
    window.Storage = StorageMock;
    const ls = new StorageMock();
    const ss = new StorageMock();
    Object.defineProperty(window, 'localStorage', { value: ls, writable: true, configurable: true });
    Object.defineProperty(window, 'sessionStorage', { value: ss, writable: true, configurable: true });
    Object.defineProperty(globalThis, 'localStorage', { value: ls, writable: true, configurable: true });
    Object.defineProperty(globalThis, 'sessionStorage', { value: ss, writable: true, configurable: true });
    Object.defineProperty(globalThis, 'Storage', { value: StorageMock, writable: true, configurable: true });
  }
}




