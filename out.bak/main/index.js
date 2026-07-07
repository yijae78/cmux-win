"use strict";
var __create = Object.create;
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __getProtoOf = Object.getPrototypeOf;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toESM = (mod2, isNodeMode, target) => (target = mod2 != null ? __create(__getProtoOf(mod2)) : {}, __copyProps(
  // If the importer is in node compatibility mode or this is not an ESM
  // file that has been converted to a CommonJS file using a Babel-
  // compatible transform (i.e. "__esModule" has not been set), then set
  // "default" to the CommonJS "module.exports" for node compatibility.
  isNodeMode || !mod2 || !mod2.__esModule ? __defProp(target, "default", { value: mod2, enumerable: true }) : target,
  mod2
));
var _a2;
const electron = require("electron");
const path = require("node:path");
const fs = require("node:fs");
const os = require("node:os");
const node_events = require("node:events");
const crypto$1 = require("node:crypto");
const net = require("node:net");
const pty = require("node-pty");
const Database = require("better-sqlite3");
const require$$1 = require("grammy");
const fs$1 = require("fs");
const path$1 = require("path");
const os$1 = require("os");
function _interopNamespaceDefault(e) {
  const n = Object.create(null, { [Symbol.toStringTag]: { value: "Module" } });
  if (e) {
    for (const k in e) {
      if (k !== "default") {
        const d = Object.getOwnPropertyDescriptor(e, k);
        Object.defineProperty(n, k, d.get ? d : {
          enumerable: true,
          get: () => e[k]
        });
      }
    }
  }
  n.default = e;
  return Object.freeze(n);
}
const pty__namespace = /* @__PURE__ */ _interopNamespaceDefault(pty);
const SCHEMA_VERSION = 1;
const DEFAULT_SOCKET_PORT = 19840;
const MAX_SOCKET_PORT_RETRIES = 10;
const SESSION_SAVE_DEBOUNCE_MS = 500;
const STATE_HISTORY_MAX = 100;
const SESSION_BACKUP_SUFFIX = ".bak";
const DEFAULT_SETTINGS = {
  appearance: { theme: "system", language: "system", iconMode: "auto" },
  terminal: {
    defaultShell: "powershell",
    fontSize: 14,
    fontFamily: "Consolas",
    themeName: "Dracula",
    cursorStyle: "block"
  },
  browser: {
    searchEngine: "google",
    searchSuggestions: true,
    httpAllowlist: ["localhost", "127.0.0.1", "::1"],
    externalUrlPatterns: []
  },
  socket: { mode: "automation", port: DEFAULT_SOCKET_PORT },
  agents: {
    claudeHooksEnabled: true,
    codexHooksEnabled: true,
    geminiHooksEnabled: true,
    orchestrationMode: "auto",
    autoStartClaude: true
  },
  telegram: {
    enabled: false,
    chatId: "",
    forwardNotifications: true,
    remoteControl: true
  },
  telemetry: { enabled: true },
  updates: { autoCheck: true, channel: "stable" },
  accessibility: { screenReaderMode: false, reducedMotion: false },
  bridge: {
    enabled: true,
    basePath: "",
    heartbeatIntervalSec: 30,
    pollIntervalSec: 5
  }
};
const IPC_CHANNELS = {
  DISPATCH: "cmux:dispatch",
  QUERY_STATE: "cmux:query-state",
  GET_INITIAL_STATE: "cmux:get-initial-state",
  STATE_UPDATE: "cmux:state-update",
  WINDOW_ID: "cmux:window-id",
  PTY_WRITE: "pty:write",
  PTY_METADATA: "pty:metadata",
  PTY_SPAWN: "pty:spawn",
  PTY_RESIZE: "pty:resize",
  PTY_KILL: "pty:kill",
  PTY_HAS: "pty:has",
  PTY_DATA: "pty:data",
  PTY_EXIT: "pty:exit",
  PTY_GET_SHELLS: "pty:get-shells",
  SHORTCUT: "cmux:shortcut",
  SCROLLBACK_SAVE: "cmux:scrollback-save",
  SCROLLBACK_LOAD: "cmux:scrollback-load",
  BROWSER_EXECUTE: "cmux:browser-execute",
  BROWSER_EXECUTE_RESULT: "cmux:browser-execute-result",
  FILE_READ: "cmux:file-read",
  FILE_LIST_DIR: "cmux:file-list-dir",
  FILE_WATCH: "cmux:file-watch",
  FILE_UNWATCH: "cmux:file-unwatch",
  FILE_CHANGED: "cmux:file-changed",
  DIALOG_OPEN_FOLDER: "cmux:dialog-open-folder"
};
var NOTHING = Symbol.for("immer-nothing");
var DRAFTABLE = Symbol.for("immer-draftable");
var DRAFT_STATE = Symbol.for("immer-state");
var errors = process.env.NODE_ENV !== "production" ? [
  // All error codes, starting by 0:
  function(plugin) {
    return `The plugin for '${plugin}' has not been loaded into Immer. To enable the plugin, import and call \`enable${plugin}()\` when initializing your application.`;
  },
  function(thing) {
    return `produce can only be called on things that are draftable: plain objects, arrays, Map, Set or classes that are marked with '[immerable]: true'. Got '${thing}'`;
  },
  "This object has been frozen and should not be mutated",
  function(data) {
    return "Cannot use a proxy that has been revoked. Did you pass an object from inside an immer function to an async process? " + data;
  },
  "An immer producer returned a new value *and* modified its draft. Either return a new value *or* modify the draft.",
  "Immer forbids circular references",
  "The first or second argument to `produce` must be a function",
  "The third argument to `produce` must be a function or undefined",
  "First argument to `createDraft` must be a plain object, an array, or an immerable object",
  "First argument to `finishDraft` must be a draft returned by `createDraft`",
  function(thing) {
    return `'current' expects a draft, got: ${thing}`;
  },
  "Object.defineProperty() cannot be used on an Immer draft",
  "Object.setPrototypeOf() cannot be used on an Immer draft",
  "Immer only supports deleting array indices",
  "Immer only supports setting array indices and the 'length' property",
  function(thing) {
    return `'original' expects a draft, got: ${thing}`;
  }
  // Note: if more errors are added, the errorOffset in Patches.ts should be increased
  // See Patches.ts for additional errors
] : [];
function die(error, ...args) {
  if (process.env.NODE_ENV !== "production") {
    const e = errors[error];
    const msg = isFunction(e) ? e.apply(null, args) : e;
    throw new Error(`[Immer] ${msg}`);
  }
  throw new Error(
    `[Immer] minified error nr: ${error}. Full error at: https://bit.ly/3cXEKWf`
  );
}
var O = Object;
var getPrototypeOf = O.getPrototypeOf;
var CONSTRUCTOR = "constructor";
var PROTOTYPE = "prototype";
var CONFIGURABLE = "configurable";
var ENUMERABLE = "enumerable";
var WRITABLE = "writable";
var VALUE = "value";
var isDraft = (value) => !!value && !!value[DRAFT_STATE];
function isDraftable(value) {
  var _a3;
  if (!value)
    return false;
  return isPlainObject$1(value) || isArray(value) || !!value[DRAFTABLE] || !!((_a3 = value[CONSTRUCTOR]) == null ? void 0 : _a3[DRAFTABLE]) || isMap(value) || isSet(value);
}
var objectCtorString = O[PROTOTYPE][CONSTRUCTOR].toString();
var cachedCtorStrings = /* @__PURE__ */ new WeakMap();
function isPlainObject$1(value) {
  if (!value || !isObjectish(value))
    return false;
  const proto = getPrototypeOf(value);
  if (proto === null || proto === O[PROTOTYPE])
    return true;
  const Ctor = O.hasOwnProperty.call(proto, CONSTRUCTOR) && proto[CONSTRUCTOR];
  if (Ctor === Object)
    return true;
  if (!isFunction(Ctor))
    return false;
  let ctorString = cachedCtorStrings.get(Ctor);
  if (ctorString === void 0) {
    ctorString = Function.toString.call(Ctor);
    cachedCtorStrings.set(Ctor, ctorString);
  }
  return ctorString === objectCtorString;
}
function each(obj, iter, strict = true) {
  if (getArchtype(obj) === 0) {
    const keys = strict ? Reflect.ownKeys(obj) : O.keys(obj);
    keys.forEach((key) => {
      iter(key, obj[key], obj);
    });
  } else {
    obj.forEach((entry, index) => iter(index, entry, obj));
  }
}
function getArchtype(thing) {
  const state = thing[DRAFT_STATE];
  return state ? state.type_ : isArray(thing) ? 1 : isMap(thing) ? 2 : isSet(thing) ? 3 : 0;
}
var has = (thing, prop, type = getArchtype(thing)) => type === 2 ? thing.has(prop) : O[PROTOTYPE].hasOwnProperty.call(thing, prop);
var get = (thing, prop, type = getArchtype(thing)) => (
  // @ts-ignore
  type === 2 ? thing.get(prop) : thing[prop]
);
var set = (thing, propOrOldValue, value, type = getArchtype(thing)) => {
  if (type === 2)
    thing.set(propOrOldValue, value);
  else if (type === 3) {
    thing.add(value);
  } else
    thing[propOrOldValue] = value;
};
function is(x, y) {
  if (x === y) {
    return x !== 0 || 1 / x === 1 / y;
  } else {
    return x !== x && y !== y;
  }
}
var isArray = Array.isArray;
var isMap = (target) => target instanceof Map;
var isSet = (target) => target instanceof Set;
var isObjectish = (target) => typeof target === "object";
var isFunction = (target) => typeof target === "function";
var isBoolean = (target) => typeof target === "boolean";
function isArrayIndex(value) {
  const n = +value;
  return Number.isInteger(n) && String(n) === value;
}
var latest = (state) => state.copy_ || state.base_;
var getFinalValue = (state) => state.modified_ ? state.copy_ : state.base_;
function shallowCopy(base, strict) {
  if (isMap(base)) {
    return new Map(base);
  }
  if (isSet(base)) {
    return new Set(base);
  }
  if (isArray(base))
    return Array[PROTOTYPE].slice.call(base);
  const isPlain = isPlainObject$1(base);
  if (strict === true || strict === "class_only" && !isPlain) {
    const descriptors = O.getOwnPropertyDescriptors(base);
    delete descriptors[DRAFT_STATE];
    let keys = Reflect.ownKeys(descriptors);
    for (let i = 0; i < keys.length; i++) {
      const key = keys[i];
      const desc = descriptors[key];
      if (desc[WRITABLE] === false) {
        desc[WRITABLE] = true;
        desc[CONFIGURABLE] = true;
      }
      if (desc.get || desc.set)
        descriptors[key] = {
          [CONFIGURABLE]: true,
          [WRITABLE]: true,
          // could live with !!desc.set as well here...
          [ENUMERABLE]: desc[ENUMERABLE],
          [VALUE]: base[key]
        };
    }
    return O.create(getPrototypeOf(base), descriptors);
  } else {
    const proto = getPrototypeOf(base);
    if (proto !== null && isPlain) {
      return { ...base };
    }
    const obj = O.create(proto);
    return O.assign(obj, base);
  }
}
function freeze(obj, deep = false) {
  if (isFrozen(obj) || isDraft(obj) || !isDraftable(obj))
    return obj;
  if (getArchtype(obj) > 1) {
    O.defineProperties(obj, {
      set: dontMutateMethodOverride,
      add: dontMutateMethodOverride,
      clear: dontMutateMethodOverride,
      delete: dontMutateMethodOverride
    });
  }
  O.freeze(obj);
  if (deep)
    each(
      obj,
      (_key, value) => {
        freeze(value, true);
      },
      false
    );
  return obj;
}
function dontMutateFrozenCollections() {
  die(2);
}
var dontMutateMethodOverride = {
  [VALUE]: dontMutateFrozenCollections
};
function isFrozen(obj) {
  if (obj === null || !isObjectish(obj))
    return true;
  return O.isFrozen(obj);
}
var PluginMapSet = "MapSet";
var PluginPatches = "Patches";
var PluginArrayMethods = "ArrayMethods";
var plugins = {};
function getPlugin(pluginKey) {
  const plugin = plugins[pluginKey];
  if (!plugin) {
    die(0, pluginKey);
  }
  return plugin;
}
var isPluginLoaded = (pluginKey) => !!plugins[pluginKey];
var currentScope;
var getCurrentScope = () => currentScope;
var createScope = (parent_, immer_) => ({
  drafts_: [],
  parent_,
  immer_,
  // Whenever the modified draft contains a draft from another scope, we
  // need to prevent auto-freezing so the unowned draft can be finalized.
  canAutoFreeze_: true,
  unfinalizedDrafts_: 0,
  handledSet_: /* @__PURE__ */ new Set(),
  processedForPatches_: /* @__PURE__ */ new Set(),
  mapSetPlugin_: isPluginLoaded(PluginMapSet) ? getPlugin(PluginMapSet) : void 0,
  arrayMethodsPlugin_: isPluginLoaded(PluginArrayMethods) ? getPlugin(PluginArrayMethods) : void 0
});
function usePatchesInScope(scope, patchListener) {
  if (patchListener) {
    scope.patchPlugin_ = getPlugin(PluginPatches);
    scope.patches_ = [];
    scope.inversePatches_ = [];
    scope.patchListener_ = patchListener;
  }
}
function revokeScope(scope) {
  leaveScope(scope);
  scope.drafts_.forEach(revokeDraft);
  scope.drafts_ = null;
}
function leaveScope(scope) {
  if (scope === currentScope) {
    currentScope = scope.parent_;
  }
}
var enterScope = (immer2) => currentScope = createScope(currentScope, immer2);
function revokeDraft(draft) {
  const state = draft[DRAFT_STATE];
  if (state.type_ === 0 || state.type_ === 1)
    state.revoke_();
  else
    state.revoked_ = true;
}
function processResult(result, scope) {
  scope.unfinalizedDrafts_ = scope.drafts_.length;
  const baseDraft = scope.drafts_[0];
  const isReplaced = result !== void 0 && result !== baseDraft;
  if (isReplaced) {
    if (baseDraft[DRAFT_STATE].modified_) {
      revokeScope(scope);
      die(4);
    }
    if (isDraftable(result)) {
      result = finalize$1(scope, result);
    }
    const { patchPlugin_ } = scope;
    if (patchPlugin_) {
      patchPlugin_.generateReplacementPatches_(
        baseDraft[DRAFT_STATE].base_,
        result,
        scope
      );
    }
  } else {
    result = finalize$1(scope, baseDraft);
  }
  maybeFreeze(scope, result, true);
  revokeScope(scope);
  if (scope.patches_) {
    scope.patchListener_(scope.patches_, scope.inversePatches_);
  }
  return result !== NOTHING ? result : void 0;
}
function finalize$1(rootScope, value) {
  if (isFrozen(value))
    return value;
  const state = value[DRAFT_STATE];
  if (!state) {
    const finalValue = handleValue(value, rootScope.handledSet_, rootScope);
    return finalValue;
  }
  if (!isSameScope(state, rootScope)) {
    return value;
  }
  if (!state.modified_) {
    return state.base_;
  }
  if (!state.finalized_) {
    const { callbacks_ } = state;
    if (callbacks_) {
      while (callbacks_.length > 0) {
        const callback = callbacks_.pop();
        callback(rootScope);
      }
    }
    generatePatchesAndFinalize(state, rootScope);
  }
  return state.copy_;
}
function maybeFreeze(scope, value, deep = false) {
  if (!scope.parent_ && scope.immer_.autoFreeze_ && scope.canAutoFreeze_) {
    freeze(value, deep);
  }
}
function markStateFinalized(state) {
  state.finalized_ = true;
  state.scope_.unfinalizedDrafts_--;
}
var isSameScope = (state, rootScope) => state.scope_ === rootScope;
var EMPTY_LOCATIONS_RESULT = [];
function updateDraftInParent(parent, draftValue, finalizedValue, originalKey) {
  const parentCopy = latest(parent);
  const parentType = parent.type_;
  if (originalKey !== void 0) {
    const currentValue = get(parentCopy, originalKey, parentType);
    if (currentValue === draftValue) {
      set(parentCopy, originalKey, finalizedValue, parentType);
      return;
    }
  }
  if (!parent.draftLocations_) {
    const draftLocations = parent.draftLocations_ = /* @__PURE__ */ new Map();
    each(parentCopy, (key, value) => {
      if (isDraft(value)) {
        const keys = draftLocations.get(value) || [];
        keys.push(key);
        draftLocations.set(value, keys);
      }
    });
  }
  const locations = parent.draftLocations_.get(draftValue) ?? EMPTY_LOCATIONS_RESULT;
  for (const location of locations) {
    set(parentCopy, location, finalizedValue, parentType);
  }
}
function registerChildFinalizationCallback(parent, child, key) {
  parent.callbacks_.push(function childCleanup(rootScope) {
    var _a3;
    const state = child;
    if (!state || !isSameScope(state, rootScope)) {
      return;
    }
    (_a3 = rootScope.mapSetPlugin_) == null ? void 0 : _a3.fixSetContents(state);
    const finalizedValue = getFinalValue(state);
    updateDraftInParent(parent, state.draft_ ?? state, finalizedValue, key);
    generatePatchesAndFinalize(state, rootScope);
  });
}
function generatePatchesAndFinalize(state, rootScope) {
  var _a3;
  const shouldFinalize = state.modified_ && !state.finalized_ && (state.type_ === 3 || state.type_ === 1 && state.allIndicesReassigned_ || (((_a3 = state.assigned_) == null ? void 0 : _a3.size) ?? 0) > 0);
  if (shouldFinalize) {
    const { patchPlugin_ } = rootScope;
    if (patchPlugin_) {
      const basePath = patchPlugin_.getPath(state);
      if (basePath) {
        patchPlugin_.generatePatches_(state, basePath, rootScope);
      }
    }
    markStateFinalized(state);
  }
}
function handleCrossReference(target, key, value) {
  const { scope_ } = target;
  if (isDraft(value)) {
    const state = value[DRAFT_STATE];
    if (isSameScope(state, scope_)) {
      state.callbacks_.push(function crossReferenceCleanup() {
        prepareCopy(target);
        const finalizedValue = getFinalValue(state);
        updateDraftInParent(target, value, finalizedValue, key);
      });
    }
  } else if (isDraftable(value)) {
    target.callbacks_.push(function nestedDraftCleanup() {
      const targetCopy = latest(target);
      if (target.type_ === 3) {
        if (targetCopy.has(value)) {
          handleValue(value, scope_.handledSet_, scope_);
        }
      } else {
        if (get(targetCopy, key, target.type_) === value) {
          if (scope_.drafts_.length > 1 && (target.assigned_.get(key) ?? false) === true && target.copy_) {
            handleValue(
              get(target.copy_, key, target.type_),
              scope_.handledSet_,
              scope_
            );
          }
        }
      }
    });
  }
}
function handleValue(target, handledSet, rootScope) {
  if (!rootScope.immer_.autoFreeze_ && rootScope.unfinalizedDrafts_ < 1) {
    return target;
  }
  if (isDraft(target) || handledSet.has(target) || !isDraftable(target) || isFrozen(target)) {
    return target;
  }
  handledSet.add(target);
  each(target, (key, value) => {
    if (isDraft(value)) {
      const state = value[DRAFT_STATE];
      if (isSameScope(state, rootScope)) {
        const updatedValue = getFinalValue(state);
        set(target, key, updatedValue, target.type_);
        markStateFinalized(state);
      }
    } else if (isDraftable(value)) {
      handleValue(value, handledSet, rootScope);
    }
  });
  return target;
}
function createProxyProxy(base, parent) {
  const baseIsArray = isArray(base);
  const state = {
    type_: baseIsArray ? 1 : 0,
    // Track which produce call this is associated with.
    scope_: parent ? parent.scope_ : getCurrentScope(),
    // True for both shallow and deep changes.
    modified_: false,
    // Used during finalization.
    finalized_: false,
    // Track which properties have been assigned (true) or deleted (false).
    // actually instantiated in `prepareCopy()`
    assigned_: void 0,
    // The parent draft state.
    parent_: parent,
    // The base state.
    base_: base,
    // The base proxy.
    draft_: null,
    // set below
    // The base copy with any updated values.
    copy_: null,
    // Called by the `produce` function.
    revoke_: null,
    isManual_: false,
    // `callbacks` actually gets assigned in `createProxy`
    callbacks_: void 0
  };
  let target = state;
  let traps = objectTraps;
  if (baseIsArray) {
    target = [state];
    traps = arrayTraps;
  }
  const { revoke, proxy } = Proxy.revocable(target, traps);
  state.draft_ = proxy;
  state.revoke_ = revoke;
  return [proxy, state];
}
var objectTraps = {
  get(state, prop) {
    if (prop === DRAFT_STATE)
      return state;
    let arrayPlugin = state.scope_.arrayMethodsPlugin_;
    const isArrayWithStringProp = state.type_ === 1 && typeof prop === "string";
    if (isArrayWithStringProp) {
      if (arrayPlugin == null ? void 0 : arrayPlugin.isArrayOperationMethod(prop)) {
        return arrayPlugin.createMethodInterceptor(state, prop);
      }
    }
    const source = latest(state);
    if (!has(source, prop, state.type_)) {
      return readPropFromProto(state, source, prop);
    }
    const value = source[prop];
    if (state.finalized_ || !isDraftable(value)) {
      return value;
    }
    if (isArrayWithStringProp && state.operationMethod && (arrayPlugin == null ? void 0 : arrayPlugin.isMutatingArrayMethod(
      state.operationMethod
    )) && isArrayIndex(prop)) {
      return value;
    }
    if (value === peek(state.base_, prop)) {
      prepareCopy(state);
      const childKey = state.type_ === 1 ? +prop : prop;
      const childDraft = createProxy(state.scope_, value, state, childKey);
      return state.copy_[childKey] = childDraft;
    }
    return value;
  },
  has(state, prop) {
    return prop in latest(state);
  },
  ownKeys(state) {
    return Reflect.ownKeys(latest(state));
  },
  set(state, prop, value) {
    const desc = getDescriptorFromProto(latest(state), prop);
    if (desc == null ? void 0 : desc.set) {
      desc.set.call(state.draft_, value);
      return true;
    }
    if (!state.modified_) {
      const current2 = peek(latest(state), prop);
      const currentState = current2 == null ? void 0 : current2[DRAFT_STATE];
      if (currentState && currentState.base_ === value) {
        state.copy_[prop] = value;
        state.assigned_.set(prop, false);
        return true;
      }
      if (is(value, current2) && (value !== void 0 || has(state.base_, prop, state.type_)))
        return true;
      prepareCopy(state);
      markChanged(state);
    }
    if (state.copy_[prop] === value && // special case: handle new props with value 'undefined'
    (value !== void 0 || prop in state.copy_) || // special case: NaN
    Number.isNaN(value) && Number.isNaN(state.copy_[prop]))
      return true;
    state.copy_[prop] = value;
    state.assigned_.set(prop, true);
    handleCrossReference(state, prop, value);
    return true;
  },
  deleteProperty(state, prop) {
    prepareCopy(state);
    if (peek(state.base_, prop) !== void 0 || prop in state.base_) {
      state.assigned_.set(prop, false);
      markChanged(state);
    } else {
      state.assigned_.delete(prop);
    }
    if (state.copy_) {
      delete state.copy_[prop];
    }
    return true;
  },
  // Note: We never coerce `desc.value` into an Immer draft, because we can't make
  // the same guarantee in ES5 mode.
  getOwnPropertyDescriptor(state, prop) {
    const owner = latest(state);
    const desc = Reflect.getOwnPropertyDescriptor(owner, prop);
    if (!desc)
      return desc;
    return {
      [WRITABLE]: true,
      [CONFIGURABLE]: state.type_ !== 1 || prop !== "length",
      [ENUMERABLE]: desc[ENUMERABLE],
      [VALUE]: owner[prop]
    };
  },
  defineProperty() {
    die(11);
  },
  getPrototypeOf(state) {
    return getPrototypeOf(state.base_);
  },
  setPrototypeOf() {
    die(12);
  }
};
var arrayTraps = {};
for (let key in objectTraps) {
  let fn = objectTraps[key];
  arrayTraps[key] = function() {
    const args = arguments;
    args[0] = args[0][0];
    return fn.apply(this, args);
  };
}
arrayTraps.deleteProperty = function(state, prop) {
  if (process.env.NODE_ENV !== "production" && isNaN(parseInt(prop)))
    die(13);
  return arrayTraps.set.call(this, state, prop, void 0);
};
arrayTraps.set = function(state, prop, value) {
  if (process.env.NODE_ENV !== "production" && prop !== "length" && isNaN(parseInt(prop)))
    die(14);
  return objectTraps.set.call(this, state[0], prop, value, state[0]);
};
function peek(draft, prop) {
  const state = draft[DRAFT_STATE];
  const source = state ? latest(state) : draft;
  return source[prop];
}
function readPropFromProto(state, source, prop) {
  var _a3;
  const desc = getDescriptorFromProto(source, prop);
  return desc ? VALUE in desc ? desc[VALUE] : (
    // This is a very special case, if the prop is a getter defined by the
    // prototype, we should invoke it with the draft as context!
    (_a3 = desc.get) == null ? void 0 : _a3.call(state.draft_)
  ) : void 0;
}
function getDescriptorFromProto(source, prop) {
  if (!(prop in source))
    return void 0;
  let proto = getPrototypeOf(source);
  while (proto) {
    const desc = Object.getOwnPropertyDescriptor(proto, prop);
    if (desc)
      return desc;
    proto = getPrototypeOf(proto);
  }
  return void 0;
}
function markChanged(state) {
  if (!state.modified_) {
    state.modified_ = true;
    if (state.parent_) {
      markChanged(state.parent_);
    }
  }
}
function prepareCopy(state) {
  if (!state.copy_) {
    state.assigned_ = /* @__PURE__ */ new Map();
    state.copy_ = shallowCopy(
      state.base_,
      state.scope_.immer_.useStrictShallowCopy_
    );
  }
}
var Immer2 = class {
  constructor(config2) {
    this.autoFreeze_ = true;
    this.useStrictShallowCopy_ = false;
    this.useStrictIteration_ = false;
    this.produce = (base, recipe, patchListener) => {
      if (isFunction(base) && !isFunction(recipe)) {
        const defaultBase = recipe;
        recipe = base;
        const self = this;
        return function curriedProduce(base2 = defaultBase, ...args) {
          return self.produce(base2, (draft) => recipe.call(this, draft, ...args));
        };
      }
      if (!isFunction(recipe))
        die(6);
      if (patchListener !== void 0 && !isFunction(patchListener))
        die(7);
      let result;
      if (isDraftable(base)) {
        const scope = enterScope(this);
        const proxy = createProxy(scope, base, void 0);
        let hasError = true;
        try {
          result = recipe(proxy);
          hasError = false;
        } finally {
          if (hasError)
            revokeScope(scope);
          else
            leaveScope(scope);
        }
        usePatchesInScope(scope, patchListener);
        return processResult(result, scope);
      } else if (!base || !isObjectish(base)) {
        result = recipe(base);
        if (result === void 0)
          result = base;
        if (result === NOTHING)
          result = void 0;
        if (this.autoFreeze_)
          freeze(result, true);
        if (patchListener) {
          const p = [];
          const ip = [];
          getPlugin(PluginPatches).generateReplacementPatches_(base, result, {
            patches_: p,
            inversePatches_: ip
          });
          patchListener(p, ip);
        }
        return result;
      } else
        die(1, base);
    };
    this.produceWithPatches = (base, recipe) => {
      if (isFunction(base)) {
        return (state, ...args) => this.produceWithPatches(state, (draft) => base(draft, ...args));
      }
      let patches, inversePatches;
      const result = this.produce(base, recipe, (p, ip) => {
        patches = p;
        inversePatches = ip;
      });
      return [result, patches, inversePatches];
    };
    if (isBoolean(config2 == null ? void 0 : config2.autoFreeze))
      this.setAutoFreeze(config2.autoFreeze);
    if (isBoolean(config2 == null ? void 0 : config2.useStrictShallowCopy))
      this.setUseStrictShallowCopy(config2.useStrictShallowCopy);
    if (isBoolean(config2 == null ? void 0 : config2.useStrictIteration))
      this.setUseStrictIteration(config2.useStrictIteration);
  }
  createDraft(base) {
    if (!isDraftable(base))
      die(8);
    if (isDraft(base))
      base = current(base);
    const scope = enterScope(this);
    const proxy = createProxy(scope, base, void 0);
    proxy[DRAFT_STATE].isManual_ = true;
    leaveScope(scope);
    return proxy;
  }
  finishDraft(draft, patchListener) {
    const state = draft && draft[DRAFT_STATE];
    if (!state || !state.isManual_)
      die(9);
    const { scope_: scope } = state;
    usePatchesInScope(scope, patchListener);
    return processResult(void 0, scope);
  }
  /**
   * Pass true to automatically freeze all copies created by Immer.
   *
   * By default, auto-freezing is enabled.
   */
  setAutoFreeze(value) {
    this.autoFreeze_ = value;
  }
  /**
   * Pass true to enable strict shallow copy.
   *
   * By default, immer does not copy the object descriptors such as getter, setter and non-enumrable properties.
   */
  setUseStrictShallowCopy(value) {
    this.useStrictShallowCopy_ = value;
  }
  /**
   * Pass false to use faster iteration that skips non-enumerable properties
   * but still handles symbols for compatibility.
   *
   * By default, strict iteration is enabled (includes all own properties).
   */
  setUseStrictIteration(value) {
    this.useStrictIteration_ = value;
  }
  shouldUseStrictIteration() {
    return this.useStrictIteration_;
  }
  applyPatches(base, patches) {
    let i;
    for (i = patches.length - 1; i >= 0; i--) {
      const patch = patches[i];
      if (patch.path.length === 0 && patch.op === "replace") {
        base = patch.value;
        break;
      }
    }
    if (i > -1) {
      patches = patches.slice(i + 1);
    }
    const applyPatchesImpl = getPlugin(PluginPatches).applyPatches_;
    if (isDraft(base)) {
      return applyPatchesImpl(base, patches);
    }
    return this.produce(
      base,
      (draft) => applyPatchesImpl(draft, patches)
    );
  }
};
function createProxy(rootScope, value, parent, key) {
  const [draft, state] = isMap(value) ? getPlugin(PluginMapSet).proxyMap_(value, parent) : isSet(value) ? getPlugin(PluginMapSet).proxySet_(value, parent) : createProxyProxy(value, parent);
  const scope = (parent == null ? void 0 : parent.scope_) ?? getCurrentScope();
  scope.drafts_.push(draft);
  state.callbacks_ = (parent == null ? void 0 : parent.callbacks_) ?? [];
  state.key_ = key;
  if (parent && key !== void 0) {
    registerChildFinalizationCallback(parent, state, key);
  } else {
    state.callbacks_.push(function rootDraftCleanup(rootScope2) {
      var _a3;
      (_a3 = rootScope2.mapSetPlugin_) == null ? void 0 : _a3.fixSetContents(state);
      const { patchPlugin_ } = rootScope2;
      if (state.modified_ && patchPlugin_) {
        patchPlugin_.generatePatches_(state, [], rootScope2);
      }
    });
  }
  return draft;
}
function current(value) {
  if (!isDraft(value))
    die(10, value);
  return currentImpl(value);
}
function currentImpl(value) {
  if (!isDraftable(value) || isFrozen(value))
    return value;
  const state = value[DRAFT_STATE];
  let copy;
  let strict = true;
  if (state) {
    if (!state.modified_)
      return state.base_;
    state.finalized_ = true;
    copy = shallowCopy(value, state.scope_.immer_.useStrictShallowCopy_);
    strict = state.scope_.immer_.shouldUseStrictIteration();
  } else {
    copy = shallowCopy(value, true);
  }
  each(
    copy,
    (key, childValue) => {
      set(copy, key, currentImpl(childValue));
    },
    strict
  );
  if (state) {
    state.finalized_ = false;
  }
  return copy;
}
var immer = new Immer2();
var produce = immer.produce;
function $constructor(name, initializer2, params) {
  function init(inst, def) {
    if (!inst._zod) {
      Object.defineProperty(inst, "_zod", {
        value: {
          def,
          constr: _,
          traits: /* @__PURE__ */ new Set()
        },
        enumerable: false
      });
    }
    if (inst._zod.traits.has(name)) {
      return;
    }
    inst._zod.traits.add(name);
    initializer2(inst, def);
    const proto = _.prototype;
    const keys = Object.keys(proto);
    for (let i = 0; i < keys.length; i++) {
      const k = keys[i];
      if (!(k in inst)) {
        inst[k] = proto[k].bind(inst);
      }
    }
  }
  const Parent = (params == null ? void 0 : params.Parent) ?? Object;
  class Definition extends Parent {
  }
  Object.defineProperty(Definition, "name", { value: name });
  function _(def) {
    var _a3;
    const inst = (params == null ? void 0 : params.Parent) ? new Definition() : this;
    init(inst, def);
    (_a3 = inst._zod).deferred ?? (_a3.deferred = []);
    for (const fn of inst._zod.deferred) {
      fn();
    }
    return inst;
  }
  Object.defineProperty(_, "init", { value: init });
  Object.defineProperty(_, Symbol.hasInstance, {
    value: (inst) => {
      var _a3, _b;
      if ((params == null ? void 0 : params.Parent) && inst instanceof params.Parent)
        return true;
      return (_b = (_a3 = inst == null ? void 0 : inst._zod) == null ? void 0 : _a3.traits) == null ? void 0 : _b.has(name);
    }
  });
  Object.defineProperty(_, "name", { value: name });
  return _;
}
class $ZodAsyncError extends Error {
  constructor() {
    super(`Encountered Promise during synchronous parse. Use .parseAsync() instead.`);
  }
}
class $ZodEncodeError extends Error {
  constructor(name) {
    super(`Encountered unidirectional transform during encode: ${name}`);
    this.name = "ZodEncodeError";
  }
}
const globalConfig = {};
function config(newConfig) {
  return globalConfig;
}
function getEnumValues(entries) {
  const numericValues = Object.values(entries).filter((v) => typeof v === "number");
  const values = Object.entries(entries).filter(([k, _]) => numericValues.indexOf(+k) === -1).map(([_, v]) => v);
  return values;
}
function jsonStringifyReplacer(_, value) {
  if (typeof value === "bigint")
    return value.toString();
  return value;
}
function cached(getter) {
  return {
    get value() {
      {
        const value = getter();
        Object.defineProperty(this, "value", { value });
        return value;
      }
    }
  };
}
function nullish(input) {
  return input === null || input === void 0;
}
function cleanRegex(source) {
  const start = source.startsWith("^") ? 1 : 0;
  const end = source.endsWith("$") ? source.length - 1 : source.length;
  return source.slice(start, end);
}
function floatSafeRemainder(val, step) {
  const valDecCount = (val.toString().split(".")[1] || "").length;
  const stepString = step.toString();
  let stepDecCount = (stepString.split(".")[1] || "").length;
  if (stepDecCount === 0 && /\d?e-\d?/.test(stepString)) {
    const match = stepString.match(/\d?e-(\d?)/);
    if (match == null ? void 0 : match[1]) {
      stepDecCount = Number.parseInt(match[1]);
    }
  }
  const decCount = valDecCount > stepDecCount ? valDecCount : stepDecCount;
  const valInt = Number.parseInt(val.toFixed(decCount).replace(".", ""));
  const stepInt = Number.parseInt(step.toFixed(decCount).replace(".", ""));
  return valInt % stepInt / 10 ** decCount;
}
const EVALUATING = Symbol("evaluating");
function defineLazy(object2, key, getter) {
  let value = void 0;
  Object.defineProperty(object2, key, {
    get() {
      if (value === EVALUATING) {
        return void 0;
      }
      if (value === void 0) {
        value = EVALUATING;
        value = getter();
      }
      return value;
    },
    set(v) {
      Object.defineProperty(object2, key, {
        value: v
        // configurable: true,
      });
    },
    configurable: true
  });
}
function assignProp(target, prop, value) {
  Object.defineProperty(target, prop, {
    value,
    writable: true,
    enumerable: true,
    configurable: true
  });
}
function mergeDefs(...defs) {
  const mergedDescriptors = {};
  for (const def of defs) {
    const descriptors = Object.getOwnPropertyDescriptors(def);
    Object.assign(mergedDescriptors, descriptors);
  }
  return Object.defineProperties({}, mergedDescriptors);
}
function esc(str) {
  return JSON.stringify(str);
}
function slugify(input) {
  return input.toLowerCase().trim().replace(/[^\w\s-]/g, "").replace(/[\s_-]+/g, "-").replace(/^-+|-+$/g, "");
}
const captureStackTrace = "captureStackTrace" in Error ? Error.captureStackTrace : (..._args) => {
};
function isObject(data) {
  return typeof data === "object" && data !== null && !Array.isArray(data);
}
const allowsEval = cached(() => {
  var _a3;
  if (typeof navigator !== "undefined" && ((_a3 = navigator == null ? void 0 : navigator.userAgent) == null ? void 0 : _a3.includes("Cloudflare"))) {
    return false;
  }
  try {
    const F = Function;
    new F("");
    return true;
  } catch (_) {
    return false;
  }
});
function isPlainObject(o) {
  if (isObject(o) === false)
    return false;
  const ctor = o.constructor;
  if (ctor === void 0)
    return true;
  if (typeof ctor !== "function")
    return true;
  const prot = ctor.prototype;
  if (isObject(prot) === false)
    return false;
  if (Object.prototype.hasOwnProperty.call(prot, "isPrototypeOf") === false) {
    return false;
  }
  return true;
}
function shallowClone(o) {
  if (isPlainObject(o))
    return { ...o };
  if (Array.isArray(o))
    return [...o];
  return o;
}
const propertyKeyTypes = /* @__PURE__ */ new Set(["string", "number", "symbol"]);
function escapeRegex(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
function clone(inst, def, params) {
  const cl = new inst._zod.constr(def ?? inst._zod.def);
  if (!def || (params == null ? void 0 : params.parent))
    cl._zod.parent = inst;
  return cl;
}
function normalizeParams(_params) {
  const params = _params;
  if (!params)
    return {};
  if (typeof params === "string")
    return { error: () => params };
  if ((params == null ? void 0 : params.message) !== void 0) {
    if ((params == null ? void 0 : params.error) !== void 0)
      throw new Error("Cannot specify both `message` and `error` params");
    params.error = params.message;
  }
  delete params.message;
  if (typeof params.error === "string")
    return { ...params, error: () => params.error };
  return params;
}
function optionalKeys(shape) {
  return Object.keys(shape).filter((k) => {
    return shape[k]._zod.optin === "optional" && shape[k]._zod.optout === "optional";
  });
}
const NUMBER_FORMAT_RANGES = {
  safeint: [Number.MIN_SAFE_INTEGER, Number.MAX_SAFE_INTEGER],
  int32: [-2147483648, 2147483647],
  uint32: [0, 4294967295],
  float32: [-34028234663852886e22, 34028234663852886e22],
  float64: [-Number.MAX_VALUE, Number.MAX_VALUE]
};
function pick(schema, mask) {
  const currDef = schema._zod.def;
  const checks = currDef.checks;
  const hasChecks = checks && checks.length > 0;
  if (hasChecks) {
    throw new Error(".pick() cannot be used on object schemas containing refinements");
  }
  const def = mergeDefs(schema._zod.def, {
    get shape() {
      const newShape = {};
      for (const key in mask) {
        if (!(key in currDef.shape)) {
          throw new Error(`Unrecognized key: "${key}"`);
        }
        if (!mask[key])
          continue;
        newShape[key] = currDef.shape[key];
      }
      assignProp(this, "shape", newShape);
      return newShape;
    },
    checks: []
  });
  return clone(schema, def);
}
function omit(schema, mask) {
  const currDef = schema._zod.def;
  const checks = currDef.checks;
  const hasChecks = checks && checks.length > 0;
  if (hasChecks) {
    throw new Error(".omit() cannot be used on object schemas containing refinements");
  }
  const def = mergeDefs(schema._zod.def, {
    get shape() {
      const newShape = { ...schema._zod.def.shape };
      for (const key in mask) {
        if (!(key in currDef.shape)) {
          throw new Error(`Unrecognized key: "${key}"`);
        }
        if (!mask[key])
          continue;
        delete newShape[key];
      }
      assignProp(this, "shape", newShape);
      return newShape;
    },
    checks: []
  });
  return clone(schema, def);
}
function extend(schema, shape) {
  if (!isPlainObject(shape)) {
    throw new Error("Invalid input to extend: expected a plain object");
  }
  const checks = schema._zod.def.checks;
  const hasChecks = checks && checks.length > 0;
  if (hasChecks) {
    const existingShape = schema._zod.def.shape;
    for (const key in shape) {
      if (Object.getOwnPropertyDescriptor(existingShape, key) !== void 0) {
        throw new Error("Cannot overwrite keys on object schemas containing refinements. Use `.safeExtend()` instead.");
      }
    }
  }
  const def = mergeDefs(schema._zod.def, {
    get shape() {
      const _shape = { ...schema._zod.def.shape, ...shape };
      assignProp(this, "shape", _shape);
      return _shape;
    }
  });
  return clone(schema, def);
}
function safeExtend(schema, shape) {
  if (!isPlainObject(shape)) {
    throw new Error("Invalid input to safeExtend: expected a plain object");
  }
  const def = mergeDefs(schema._zod.def, {
    get shape() {
      const _shape = { ...schema._zod.def.shape, ...shape };
      assignProp(this, "shape", _shape);
      return _shape;
    }
  });
  return clone(schema, def);
}
function merge(a, b) {
  const def = mergeDefs(a._zod.def, {
    get shape() {
      const _shape = { ...a._zod.def.shape, ...b._zod.def.shape };
      assignProp(this, "shape", _shape);
      return _shape;
    },
    get catchall() {
      return b._zod.def.catchall;
    },
    checks: []
    // delete existing checks
  });
  return clone(a, def);
}
function partial(Class, schema, mask) {
  const currDef = schema._zod.def;
  const checks = currDef.checks;
  const hasChecks = checks && checks.length > 0;
  if (hasChecks) {
    throw new Error(".partial() cannot be used on object schemas containing refinements");
  }
  const def = mergeDefs(schema._zod.def, {
    get shape() {
      const oldShape = schema._zod.def.shape;
      const shape = { ...oldShape };
      if (mask) {
        for (const key in mask) {
          if (!(key in oldShape)) {
            throw new Error(`Unrecognized key: "${key}"`);
          }
          if (!mask[key])
            continue;
          shape[key] = Class ? new Class({
            type: "optional",
            innerType: oldShape[key]
          }) : oldShape[key];
        }
      } else {
        for (const key in oldShape) {
          shape[key] = Class ? new Class({
            type: "optional",
            innerType: oldShape[key]
          }) : oldShape[key];
        }
      }
      assignProp(this, "shape", shape);
      return shape;
    },
    checks: []
  });
  return clone(schema, def);
}
function required(Class, schema, mask) {
  const def = mergeDefs(schema._zod.def, {
    get shape() {
      const oldShape = schema._zod.def.shape;
      const shape = { ...oldShape };
      if (mask) {
        for (const key in mask) {
          if (!(key in shape)) {
            throw new Error(`Unrecognized key: "${key}"`);
          }
          if (!mask[key])
            continue;
          shape[key] = new Class({
            type: "nonoptional",
            innerType: oldShape[key]
          });
        }
      } else {
        for (const key in oldShape) {
          shape[key] = new Class({
            type: "nonoptional",
            innerType: oldShape[key]
          });
        }
      }
      assignProp(this, "shape", shape);
      return shape;
    }
  });
  return clone(schema, def);
}
function aborted(x, startIndex = 0) {
  var _a3;
  if (x.aborted === true)
    return true;
  for (let i = startIndex; i < x.issues.length; i++) {
    if (((_a3 = x.issues[i]) == null ? void 0 : _a3.continue) !== true) {
      return true;
    }
  }
  return false;
}
function prefixIssues(path2, issues) {
  return issues.map((iss) => {
    var _a3;
    (_a3 = iss).path ?? (_a3.path = []);
    iss.path.unshift(path2);
    return iss;
  });
}
function unwrapMessage(message) {
  return typeof message === "string" ? message : message == null ? void 0 : message.message;
}
function finalizeIssue(iss, ctx, config2) {
  var _a3, _b, _c, _d, _e, _f;
  const full = { ...iss, path: iss.path ?? [] };
  if (!iss.message) {
    const message = unwrapMessage((_c = (_b = (_a3 = iss.inst) == null ? void 0 : _a3._zod.def) == null ? void 0 : _b.error) == null ? void 0 : _c.call(_b, iss)) ?? unwrapMessage((_d = ctx == null ? void 0 : ctx.error) == null ? void 0 : _d.call(ctx, iss)) ?? unwrapMessage((_e = config2.customError) == null ? void 0 : _e.call(config2, iss)) ?? unwrapMessage((_f = config2.localeError) == null ? void 0 : _f.call(config2, iss)) ?? "Invalid input";
    full.message = message;
  }
  delete full.inst;
  delete full.continue;
  if (!(ctx == null ? void 0 : ctx.reportInput)) {
    delete full.input;
  }
  return full;
}
function getLengthableOrigin(input) {
  if (Array.isArray(input))
    return "array";
  if (typeof input === "string")
    return "string";
  return "unknown";
}
function issue(...args) {
  const [iss, input, inst] = args;
  if (typeof iss === "string") {
    return {
      message: iss,
      code: "custom",
      input,
      inst
    };
  }
  return { ...iss };
}
const initializer$1 = (inst, def) => {
  inst.name = "$ZodError";
  Object.defineProperty(inst, "_zod", {
    value: inst._zod,
    enumerable: false
  });
  Object.defineProperty(inst, "issues", {
    value: def,
    enumerable: false
  });
  inst.message = JSON.stringify(def, jsonStringifyReplacer, 2);
  Object.defineProperty(inst, "toString", {
    value: () => inst.message,
    enumerable: false
  });
};
const $ZodError = $constructor("$ZodError", initializer$1);
const $ZodRealError = $constructor("$ZodError", initializer$1, { Parent: Error });
function flattenError(error, mapper = (issue2) => issue2.message) {
  const fieldErrors = {};
  const formErrors = [];
  for (const sub of error.issues) {
    if (sub.path.length > 0) {
      fieldErrors[sub.path[0]] = fieldErrors[sub.path[0]] || [];
      fieldErrors[sub.path[0]].push(mapper(sub));
    } else {
      formErrors.push(mapper(sub));
    }
  }
  return { formErrors, fieldErrors };
}
function formatError(error, mapper = (issue2) => issue2.message) {
  const fieldErrors = { _errors: [] };
  const processError = (error2) => {
    for (const issue2 of error2.issues) {
      if (issue2.code === "invalid_union" && issue2.errors.length) {
        issue2.errors.map((issues) => processError({ issues }));
      } else if (issue2.code === "invalid_key") {
        processError({ issues: issue2.issues });
      } else if (issue2.code === "invalid_element") {
        processError({ issues: issue2.issues });
      } else if (issue2.path.length === 0) {
        fieldErrors._errors.push(mapper(issue2));
      } else {
        let curr = fieldErrors;
        let i = 0;
        while (i < issue2.path.length) {
          const el = issue2.path[i];
          const terminal = i === issue2.path.length - 1;
          if (!terminal) {
            curr[el] = curr[el] || { _errors: [] };
          } else {
            curr[el] = curr[el] || { _errors: [] };
            curr[el]._errors.push(mapper(issue2));
          }
          curr = curr[el];
          i++;
        }
      }
    }
  };
  processError(error);
  return fieldErrors;
}
const _parse = (_Err) => (schema, value, _ctx, _params) => {
  const ctx = _ctx ? Object.assign(_ctx, { async: false }) : { async: false };
  const result = schema._zod.run({ value, issues: [] }, ctx);
  if (result instanceof Promise) {
    throw new $ZodAsyncError();
  }
  if (result.issues.length) {
    const e = new ((_params == null ? void 0 : _params.Err) ?? _Err)(result.issues.map((iss) => finalizeIssue(iss, ctx, config())));
    captureStackTrace(e, _params == null ? void 0 : _params.callee);
    throw e;
  }
  return result.value;
};
const _parseAsync = (_Err) => async (schema, value, _ctx, params) => {
  const ctx = _ctx ? Object.assign(_ctx, { async: true }) : { async: true };
  let result = schema._zod.run({ value, issues: [] }, ctx);
  if (result instanceof Promise)
    result = await result;
  if (result.issues.length) {
    const e = new ((params == null ? void 0 : params.Err) ?? _Err)(result.issues.map((iss) => finalizeIssue(iss, ctx, config())));
    captureStackTrace(e, params == null ? void 0 : params.callee);
    throw e;
  }
  return result.value;
};
const _safeParse = (_Err) => (schema, value, _ctx) => {
  const ctx = _ctx ? { ..._ctx, async: false } : { async: false };
  const result = schema._zod.run({ value, issues: [] }, ctx);
  if (result instanceof Promise) {
    throw new $ZodAsyncError();
  }
  return result.issues.length ? {
    success: false,
    error: new (_Err ?? $ZodError)(result.issues.map((iss) => finalizeIssue(iss, ctx, config())))
  } : { success: true, data: result.value };
};
const safeParse$1 = /* @__PURE__ */ _safeParse($ZodRealError);
const _safeParseAsync = (_Err) => async (schema, value, _ctx) => {
  const ctx = _ctx ? Object.assign(_ctx, { async: true }) : { async: true };
  let result = schema._zod.run({ value, issues: [] }, ctx);
  if (result instanceof Promise)
    result = await result;
  return result.issues.length ? {
    success: false,
    error: new _Err(result.issues.map((iss) => finalizeIssue(iss, ctx, config())))
  } : { success: true, data: result.value };
};
const safeParseAsync$1 = /* @__PURE__ */ _safeParseAsync($ZodRealError);
const _encode = (_Err) => (schema, value, _ctx) => {
  const ctx = _ctx ? Object.assign(_ctx, { direction: "backward" }) : { direction: "backward" };
  return _parse(_Err)(schema, value, ctx);
};
const _decode = (_Err) => (schema, value, _ctx) => {
  return _parse(_Err)(schema, value, _ctx);
};
const _encodeAsync = (_Err) => async (schema, value, _ctx) => {
  const ctx = _ctx ? Object.assign(_ctx, { direction: "backward" }) : { direction: "backward" };
  return _parseAsync(_Err)(schema, value, ctx);
};
const _decodeAsync = (_Err) => async (schema, value, _ctx) => {
  return _parseAsync(_Err)(schema, value, _ctx);
};
const _safeEncode = (_Err) => (schema, value, _ctx) => {
  const ctx = _ctx ? Object.assign(_ctx, { direction: "backward" }) : { direction: "backward" };
  return _safeParse(_Err)(schema, value, ctx);
};
const _safeDecode = (_Err) => (schema, value, _ctx) => {
  return _safeParse(_Err)(schema, value, _ctx);
};
const _safeEncodeAsync = (_Err) => async (schema, value, _ctx) => {
  const ctx = _ctx ? Object.assign(_ctx, { direction: "backward" }) : { direction: "backward" };
  return _safeParseAsync(_Err)(schema, value, ctx);
};
const _safeDecodeAsync = (_Err) => async (schema, value, _ctx) => {
  return _safeParseAsync(_Err)(schema, value, _ctx);
};
const cuid = /^[cC][^\s-]{8,}$/;
const cuid2 = /^[0-9a-z]+$/;
const ulid = /^[0-9A-HJKMNP-TV-Za-hjkmnp-tv-z]{26}$/;
const xid = /^[0-9a-vA-V]{20}$/;
const ksuid = /^[A-Za-z0-9]{27}$/;
const nanoid = /^[a-zA-Z0-9_-]{21}$/;
const duration$1 = /^P(?:(\d+W)|(?!.*W)(?=\d|T\d)(\d+Y)?(\d+M)?(\d+D)?(T(?=\d)(\d+H)?(\d+M)?(\d+([.,]\d+)?S)?)?)$/;
const guid = /^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$/;
const uuid = (version2) => {
  if (!version2)
    return /^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$/;
  return new RegExp(`^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-${version2}[0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12})$`);
};
const email = /^(?!\.)(?!.*\.\.)([A-Za-z0-9_'+\-\.]*)[A-Za-z0-9_+-]@([A-Za-z0-9][A-Za-z0-9\-]*\.)+[A-Za-z]{2,}$/;
const _emoji$1 = `^(\\p{Extended_Pictographic}|\\p{Emoji_Component})+$`;
function emoji() {
  return new RegExp(_emoji$1, "u");
}
const ipv4 = /^(?:(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9][0-9]|[0-9])\.){3}(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9][0-9]|[0-9])$/;
const ipv6 = /^(([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:))$/;
const cidrv4 = /^((25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9][0-9]|[0-9])\.){3}(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9][0-9]|[0-9])\/([0-9]|[1-2][0-9]|3[0-2])$/;
const cidrv6 = /^(([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}|::|([0-9a-fA-F]{1,4})?::([0-9a-fA-F]{1,4}:?){0,6})\/(12[0-8]|1[01][0-9]|[1-9]?[0-9])$/;
const base64 = /^$|^(?:[0-9a-zA-Z+/]{4})*(?:(?:[0-9a-zA-Z+/]{2}==)|(?:[0-9a-zA-Z+/]{3}=))?$/;
const base64url = /^[A-Za-z0-9_-]*$/;
const e164 = /^\+[1-9]\d{6,14}$/;
const dateSource = `(?:(?:\\d\\d[2468][048]|\\d\\d[13579][26]|\\d\\d0[48]|[02468][048]00|[13579][26]00)-02-29|\\d{4}-(?:(?:0[13578]|1[02])-(?:0[1-9]|[12]\\d|3[01])|(?:0[469]|11)-(?:0[1-9]|[12]\\d|30)|(?:02)-(?:0[1-9]|1\\d|2[0-8])))`;
const date$1 = /* @__PURE__ */ new RegExp(`^${dateSource}$`);
function timeSource(args) {
  const hhmm = `(?:[01]\\d|2[0-3]):[0-5]\\d`;
  const regex = typeof args.precision === "number" ? args.precision === -1 ? `${hhmm}` : args.precision === 0 ? `${hhmm}:[0-5]\\d` : `${hhmm}:[0-5]\\d\\.\\d{${args.precision}}` : `${hhmm}(?::[0-5]\\d(?:\\.\\d+)?)?`;
  return regex;
}
function time$1(args) {
  return new RegExp(`^${timeSource(args)}$`);
}
function datetime$1(args) {
  const time2 = timeSource({ precision: args.precision });
  const opts = ["Z"];
  if (args.local)
    opts.push("");
  if (args.offset)
    opts.push(`([+-](?:[01]\\d|2[0-3]):[0-5]\\d)`);
  const timeRegex = `${time2}(?:${opts.join("|")})`;
  return new RegExp(`^${dateSource}T(?:${timeRegex})$`);
}
const string$1 = (params) => {
  const regex = params ? `[\\s\\S]{${(params == null ? void 0 : params.minimum) ?? 0},${(params == null ? void 0 : params.maximum) ?? ""}}` : `[\\s\\S]*`;
  return new RegExp(`^${regex}$`);
};
const integer = /^-?\d+$/;
const number$1 = /^-?\d+(?:\.\d+)?$/;
const boolean$1 = /^(?:true|false)$/i;
const lowercase = /^[^A-Z]*$/;
const uppercase = /^[^a-z]*$/;
const $ZodCheck = /* @__PURE__ */ $constructor("$ZodCheck", (inst, def) => {
  var _a3;
  inst._zod ?? (inst._zod = {});
  inst._zod.def = def;
  (_a3 = inst._zod).onattach ?? (_a3.onattach = []);
});
const numericOriginMap = {
  number: "number",
  bigint: "bigint",
  object: "date"
};
const $ZodCheckLessThan = /* @__PURE__ */ $constructor("$ZodCheckLessThan", (inst, def) => {
  $ZodCheck.init(inst, def);
  const origin = numericOriginMap[typeof def.value];
  inst._zod.onattach.push((inst2) => {
    const bag = inst2._zod.bag;
    const curr = (def.inclusive ? bag.maximum : bag.exclusiveMaximum) ?? Number.POSITIVE_INFINITY;
    if (def.value < curr) {
      if (def.inclusive)
        bag.maximum = def.value;
      else
        bag.exclusiveMaximum = def.value;
    }
  });
  inst._zod.check = (payload) => {
    if (def.inclusive ? payload.value <= def.value : payload.value < def.value) {
      return;
    }
    payload.issues.push({
      origin,
      code: "too_big",
      maximum: typeof def.value === "object" ? def.value.getTime() : def.value,
      input: payload.value,
      inclusive: def.inclusive,
      inst,
      continue: !def.abort
    });
  };
});
const $ZodCheckGreaterThan = /* @__PURE__ */ $constructor("$ZodCheckGreaterThan", (inst, def) => {
  $ZodCheck.init(inst, def);
  const origin = numericOriginMap[typeof def.value];
  inst._zod.onattach.push((inst2) => {
    const bag = inst2._zod.bag;
    const curr = (def.inclusive ? bag.minimum : bag.exclusiveMinimum) ?? Number.NEGATIVE_INFINITY;
    if (def.value > curr) {
      if (def.inclusive)
        bag.minimum = def.value;
      else
        bag.exclusiveMinimum = def.value;
    }
  });
  inst._zod.check = (payload) => {
    if (def.inclusive ? payload.value >= def.value : payload.value > def.value) {
      return;
    }
    payload.issues.push({
      origin,
      code: "too_small",
      minimum: typeof def.value === "object" ? def.value.getTime() : def.value,
      input: payload.value,
      inclusive: def.inclusive,
      inst,
      continue: !def.abort
    });
  };
});
const $ZodCheckMultipleOf = /* @__PURE__ */ $constructor("$ZodCheckMultipleOf", (inst, def) => {
  $ZodCheck.init(inst, def);
  inst._zod.onattach.push((inst2) => {
    var _a3;
    (_a3 = inst2._zod.bag).multipleOf ?? (_a3.multipleOf = def.value);
  });
  inst._zod.check = (payload) => {
    if (typeof payload.value !== typeof def.value)
      throw new Error("Cannot mix number and bigint in multiple_of check.");
    const isMultiple = typeof payload.value === "bigint" ? payload.value % def.value === BigInt(0) : floatSafeRemainder(payload.value, def.value) === 0;
    if (isMultiple)
      return;
    payload.issues.push({
      origin: typeof payload.value,
      code: "not_multiple_of",
      divisor: def.value,
      input: payload.value,
      inst,
      continue: !def.abort
    });
  };
});
const $ZodCheckNumberFormat = /* @__PURE__ */ $constructor("$ZodCheckNumberFormat", (inst, def) => {
  var _a3;
  $ZodCheck.init(inst, def);
  def.format = def.format || "float64";
  const isInt = (_a3 = def.format) == null ? void 0 : _a3.includes("int");
  const origin = isInt ? "int" : "number";
  const [minimum, maximum] = NUMBER_FORMAT_RANGES[def.format];
  inst._zod.onattach.push((inst2) => {
    const bag = inst2._zod.bag;
    bag.format = def.format;
    bag.minimum = minimum;
    bag.maximum = maximum;
    if (isInt)
      bag.pattern = integer;
  });
  inst._zod.check = (payload) => {
    const input = payload.value;
    if (isInt) {
      if (!Number.isInteger(input)) {
        payload.issues.push({
          expected: origin,
          format: def.format,
          code: "invalid_type",
          continue: false,
          input,
          inst
        });
        return;
      }
      if (!Number.isSafeInteger(input)) {
        if (input > 0) {
          payload.issues.push({
            input,
            code: "too_big",
            maximum: Number.MAX_SAFE_INTEGER,
            note: "Integers must be within the safe integer range.",
            inst,
            origin,
            inclusive: true,
            continue: !def.abort
          });
        } else {
          payload.issues.push({
            input,
            code: "too_small",
            minimum: Number.MIN_SAFE_INTEGER,
            note: "Integers must be within the safe integer range.",
            inst,
            origin,
            inclusive: true,
            continue: !def.abort
          });
        }
        return;
      }
    }
    if (input < minimum) {
      payload.issues.push({
        origin: "number",
        input,
        code: "too_small",
        minimum,
        inclusive: true,
        inst,
        continue: !def.abort
      });
    }
    if (input > maximum) {
      payload.issues.push({
        origin: "number",
        input,
        code: "too_big",
        maximum,
        inclusive: true,
        inst,
        continue: !def.abort
      });
    }
  };
});
const $ZodCheckMaxLength = /* @__PURE__ */ $constructor("$ZodCheckMaxLength", (inst, def) => {
  var _a3;
  $ZodCheck.init(inst, def);
  (_a3 = inst._zod.def).when ?? (_a3.when = (payload) => {
    const val = payload.value;
    return !nullish(val) && val.length !== void 0;
  });
  inst._zod.onattach.push((inst2) => {
    const curr = inst2._zod.bag.maximum ?? Number.POSITIVE_INFINITY;
    if (def.maximum < curr)
      inst2._zod.bag.maximum = def.maximum;
  });
  inst._zod.check = (payload) => {
    const input = payload.value;
    const length = input.length;
    if (length <= def.maximum)
      return;
    const origin = getLengthableOrigin(input);
    payload.issues.push({
      origin,
      code: "too_big",
      maximum: def.maximum,
      inclusive: true,
      input,
      inst,
      continue: !def.abort
    });
  };
});
const $ZodCheckMinLength = /* @__PURE__ */ $constructor("$ZodCheckMinLength", (inst, def) => {
  var _a3;
  $ZodCheck.init(inst, def);
  (_a3 = inst._zod.def).when ?? (_a3.when = (payload) => {
    const val = payload.value;
    return !nullish(val) && val.length !== void 0;
  });
  inst._zod.onattach.push((inst2) => {
    const curr = inst2._zod.bag.minimum ?? Number.NEGATIVE_INFINITY;
    if (def.minimum > curr)
      inst2._zod.bag.minimum = def.minimum;
  });
  inst._zod.check = (payload) => {
    const input = payload.value;
    const length = input.length;
    if (length >= def.minimum)
      return;
    const origin = getLengthableOrigin(input);
    payload.issues.push({
      origin,
      code: "too_small",
      minimum: def.minimum,
      inclusive: true,
      input,
      inst,
      continue: !def.abort
    });
  };
});
const $ZodCheckLengthEquals = /* @__PURE__ */ $constructor("$ZodCheckLengthEquals", (inst, def) => {
  var _a3;
  $ZodCheck.init(inst, def);
  (_a3 = inst._zod.def).when ?? (_a3.when = (payload) => {
    const val = payload.value;
    return !nullish(val) && val.length !== void 0;
  });
  inst._zod.onattach.push((inst2) => {
    const bag = inst2._zod.bag;
    bag.minimum = def.length;
    bag.maximum = def.length;
    bag.length = def.length;
  });
  inst._zod.check = (payload) => {
    const input = payload.value;
    const length = input.length;
    if (length === def.length)
      return;
    const origin = getLengthableOrigin(input);
    const tooBig = length > def.length;
    payload.issues.push({
      origin,
      ...tooBig ? { code: "too_big", maximum: def.length } : { code: "too_small", minimum: def.length },
      inclusive: true,
      exact: true,
      input: payload.value,
      inst,
      continue: !def.abort
    });
  };
});
const $ZodCheckStringFormat = /* @__PURE__ */ $constructor("$ZodCheckStringFormat", (inst, def) => {
  var _a3, _b;
  $ZodCheck.init(inst, def);
  inst._zod.onattach.push((inst2) => {
    const bag = inst2._zod.bag;
    bag.format = def.format;
    if (def.pattern) {
      bag.patterns ?? (bag.patterns = /* @__PURE__ */ new Set());
      bag.patterns.add(def.pattern);
    }
  });
  if (def.pattern)
    (_a3 = inst._zod).check ?? (_a3.check = (payload) => {
      def.pattern.lastIndex = 0;
      if (def.pattern.test(payload.value))
        return;
      payload.issues.push({
        origin: "string",
        code: "invalid_format",
        format: def.format,
        input: payload.value,
        ...def.pattern ? { pattern: def.pattern.toString() } : {},
        inst,
        continue: !def.abort
      });
    });
  else
    (_b = inst._zod).check ?? (_b.check = () => {
    });
});
const $ZodCheckRegex = /* @__PURE__ */ $constructor("$ZodCheckRegex", (inst, def) => {
  $ZodCheckStringFormat.init(inst, def);
  inst._zod.check = (payload) => {
    def.pattern.lastIndex = 0;
    if (def.pattern.test(payload.value))
      return;
    payload.issues.push({
      origin: "string",
      code: "invalid_format",
      format: "regex",
      input: payload.value,
      pattern: def.pattern.toString(),
      inst,
      continue: !def.abort
    });
  };
});
const $ZodCheckLowerCase = /* @__PURE__ */ $constructor("$ZodCheckLowerCase", (inst, def) => {
  def.pattern ?? (def.pattern = lowercase);
  $ZodCheckStringFormat.init(inst, def);
});
const $ZodCheckUpperCase = /* @__PURE__ */ $constructor("$ZodCheckUpperCase", (inst, def) => {
  def.pattern ?? (def.pattern = uppercase);
  $ZodCheckStringFormat.init(inst, def);
});
const $ZodCheckIncludes = /* @__PURE__ */ $constructor("$ZodCheckIncludes", (inst, def) => {
  $ZodCheck.init(inst, def);
  const escapedRegex = escapeRegex(def.includes);
  const pattern = new RegExp(typeof def.position === "number" ? `^.{${def.position}}${escapedRegex}` : escapedRegex);
  def.pattern = pattern;
  inst._zod.onattach.push((inst2) => {
    const bag = inst2._zod.bag;
    bag.patterns ?? (bag.patterns = /* @__PURE__ */ new Set());
    bag.patterns.add(pattern);
  });
  inst._zod.check = (payload) => {
    if (payload.value.includes(def.includes, def.position))
      return;
    payload.issues.push({
      origin: "string",
      code: "invalid_format",
      format: "includes",
      includes: def.includes,
      input: payload.value,
      inst,
      continue: !def.abort
    });
  };
});
const $ZodCheckStartsWith = /* @__PURE__ */ $constructor("$ZodCheckStartsWith", (inst, def) => {
  $ZodCheck.init(inst, def);
  const pattern = new RegExp(`^${escapeRegex(def.prefix)}.*`);
  def.pattern ?? (def.pattern = pattern);
  inst._zod.onattach.push((inst2) => {
    const bag = inst2._zod.bag;
    bag.patterns ?? (bag.patterns = /* @__PURE__ */ new Set());
    bag.patterns.add(pattern);
  });
  inst._zod.check = (payload) => {
    if (payload.value.startsWith(def.prefix))
      return;
    payload.issues.push({
      origin: "string",
      code: "invalid_format",
      format: "starts_with",
      prefix: def.prefix,
      input: payload.value,
      inst,
      continue: !def.abort
    });
  };
});
const $ZodCheckEndsWith = /* @__PURE__ */ $constructor("$ZodCheckEndsWith", (inst, def) => {
  $ZodCheck.init(inst, def);
  const pattern = new RegExp(`.*${escapeRegex(def.suffix)}$`);
  def.pattern ?? (def.pattern = pattern);
  inst._zod.onattach.push((inst2) => {
    const bag = inst2._zod.bag;
    bag.patterns ?? (bag.patterns = /* @__PURE__ */ new Set());
    bag.patterns.add(pattern);
  });
  inst._zod.check = (payload) => {
    if (payload.value.endsWith(def.suffix))
      return;
    payload.issues.push({
      origin: "string",
      code: "invalid_format",
      format: "ends_with",
      suffix: def.suffix,
      input: payload.value,
      inst,
      continue: !def.abort
    });
  };
});
const $ZodCheckOverwrite = /* @__PURE__ */ $constructor("$ZodCheckOverwrite", (inst, def) => {
  $ZodCheck.init(inst, def);
  inst._zod.check = (payload) => {
    payload.value = def.tx(payload.value);
  };
});
class Doc {
  constructor(args = []) {
    this.content = [];
    this.indent = 0;
    if (this)
      this.args = args;
  }
  indented(fn) {
    this.indent += 1;
    fn(this);
    this.indent -= 1;
  }
  write(arg) {
    if (typeof arg === "function") {
      arg(this, { execution: "sync" });
      arg(this, { execution: "async" });
      return;
    }
    const content = arg;
    const lines = content.split("\n").filter((x) => x);
    const minIndent = Math.min(...lines.map((x) => x.length - x.trimStart().length));
    const dedented = lines.map((x) => x.slice(minIndent)).map((x) => " ".repeat(this.indent * 2) + x);
    for (const line of dedented) {
      this.content.push(line);
    }
  }
  compile() {
    const F = Function;
    const args = this == null ? void 0 : this.args;
    const content = (this == null ? void 0 : this.content) ?? [``];
    const lines = [...content.map((x) => `  ${x}`)];
    return new F(...args, lines.join("\n"));
  }
}
const version = {
  major: 4,
  minor: 3,
  patch: 6
};
const $ZodType = /* @__PURE__ */ $constructor("$ZodType", (inst, def) => {
  var _a4;
  var _a3;
  inst ?? (inst = {});
  inst._zod.def = def;
  inst._zod.bag = inst._zod.bag || {};
  inst._zod.version = version;
  const checks = [...inst._zod.def.checks ?? []];
  if (inst._zod.traits.has("$ZodCheck")) {
    checks.unshift(inst);
  }
  for (const ch of checks) {
    for (const fn of ch._zod.onattach) {
      fn(inst);
    }
  }
  if (checks.length === 0) {
    (_a3 = inst._zod).deferred ?? (_a3.deferred = []);
    (_a4 = inst._zod.deferred) == null ? void 0 : _a4.push(() => {
      inst._zod.run = inst._zod.parse;
    });
  } else {
    const runChecks = (payload, checks2, ctx) => {
      let isAborted = aborted(payload);
      let asyncResult;
      for (const ch of checks2) {
        if (ch._zod.def.when) {
          const shouldRun = ch._zod.def.when(payload);
          if (!shouldRun)
            continue;
        } else if (isAborted) {
          continue;
        }
        const currLen = payload.issues.length;
        const _ = ch._zod.check(payload);
        if (_ instanceof Promise && (ctx == null ? void 0 : ctx.async) === false) {
          throw new $ZodAsyncError();
        }
        if (asyncResult || _ instanceof Promise) {
          asyncResult = (asyncResult ?? Promise.resolve()).then(async () => {
            await _;
            const nextLen = payload.issues.length;
            if (nextLen === currLen)
              return;
            if (!isAborted)
              isAborted = aborted(payload, currLen);
          });
        } else {
          const nextLen = payload.issues.length;
          if (nextLen === currLen)
            continue;
          if (!isAborted)
            isAborted = aborted(payload, currLen);
        }
      }
      if (asyncResult) {
        return asyncResult.then(() => {
          return payload;
        });
      }
      return payload;
    };
    const handleCanaryResult = (canary, payload, ctx) => {
      if (aborted(canary)) {
        canary.aborted = true;
        return canary;
      }
      const checkResult = runChecks(payload, checks, ctx);
      if (checkResult instanceof Promise) {
        if (ctx.async === false)
          throw new $ZodAsyncError();
        return checkResult.then((checkResult2) => inst._zod.parse(checkResult2, ctx));
      }
      return inst._zod.parse(checkResult, ctx);
    };
    inst._zod.run = (payload, ctx) => {
      if (ctx.skipChecks) {
        return inst._zod.parse(payload, ctx);
      }
      if (ctx.direction === "backward") {
        const canary = inst._zod.parse({ value: payload.value, issues: [] }, { ...ctx, skipChecks: true });
        if (canary instanceof Promise) {
          return canary.then((canary2) => {
            return handleCanaryResult(canary2, payload, ctx);
          });
        }
        return handleCanaryResult(canary, payload, ctx);
      }
      const result = inst._zod.parse(payload, ctx);
      if (result instanceof Promise) {
        if (ctx.async === false)
          throw new $ZodAsyncError();
        return result.then((result2) => runChecks(result2, checks, ctx));
      }
      return runChecks(result, checks, ctx);
    };
  }
  defineLazy(inst, "~standard", () => ({
    validate: (value) => {
      var _a5;
      try {
        const r = safeParse$1(inst, value);
        return r.success ? { value: r.data } : { issues: (_a5 = r.error) == null ? void 0 : _a5.issues };
      } catch (_) {
        return safeParseAsync$1(inst, value).then((r) => {
          var _a6;
          return r.success ? { value: r.data } : { issues: (_a6 = r.error) == null ? void 0 : _a6.issues };
        });
      }
    },
    vendor: "zod",
    version: 1
  }));
});
const $ZodString = /* @__PURE__ */ $constructor("$ZodString", (inst, def) => {
  var _a3;
  $ZodType.init(inst, def);
  inst._zod.pattern = [...((_a3 = inst == null ? void 0 : inst._zod.bag) == null ? void 0 : _a3.patterns) ?? []].pop() ?? string$1(inst._zod.bag);
  inst._zod.parse = (payload, _) => {
    if (def.coerce)
      try {
        payload.value = String(payload.value);
      } catch (_2) {
      }
    if (typeof payload.value === "string")
      return payload;
    payload.issues.push({
      expected: "string",
      code: "invalid_type",
      input: payload.value,
      inst
    });
    return payload;
  };
});
const $ZodStringFormat = /* @__PURE__ */ $constructor("$ZodStringFormat", (inst, def) => {
  $ZodCheckStringFormat.init(inst, def);
  $ZodString.init(inst, def);
});
const $ZodGUID = /* @__PURE__ */ $constructor("$ZodGUID", (inst, def) => {
  def.pattern ?? (def.pattern = guid);
  $ZodStringFormat.init(inst, def);
});
const $ZodUUID = /* @__PURE__ */ $constructor("$ZodUUID", (inst, def) => {
  if (def.version) {
    const versionMap = {
      v1: 1,
      v2: 2,
      v3: 3,
      v4: 4,
      v5: 5,
      v6: 6,
      v7: 7,
      v8: 8
    };
    const v = versionMap[def.version];
    if (v === void 0)
      throw new Error(`Invalid UUID version: "${def.version}"`);
    def.pattern ?? (def.pattern = uuid(v));
  } else
    def.pattern ?? (def.pattern = uuid());
  $ZodStringFormat.init(inst, def);
});
const $ZodEmail = /* @__PURE__ */ $constructor("$ZodEmail", (inst, def) => {
  def.pattern ?? (def.pattern = email);
  $ZodStringFormat.init(inst, def);
});
const $ZodURL = /* @__PURE__ */ $constructor("$ZodURL", (inst, def) => {
  $ZodStringFormat.init(inst, def);
  inst._zod.check = (payload) => {
    try {
      const trimmed = payload.value.trim();
      const url = new URL(trimmed);
      if (def.hostname) {
        def.hostname.lastIndex = 0;
        if (!def.hostname.test(url.hostname)) {
          payload.issues.push({
            code: "invalid_format",
            format: "url",
            note: "Invalid hostname",
            pattern: def.hostname.source,
            input: payload.value,
            inst,
            continue: !def.abort
          });
        }
      }
      if (def.protocol) {
        def.protocol.lastIndex = 0;
        if (!def.protocol.test(url.protocol.endsWith(":") ? url.protocol.slice(0, -1) : url.protocol)) {
          payload.issues.push({
            code: "invalid_format",
            format: "url",
            note: "Invalid protocol",
            pattern: def.protocol.source,
            input: payload.value,
            inst,
            continue: !def.abort
          });
        }
      }
      if (def.normalize) {
        payload.value = url.href;
      } else {
        payload.value = trimmed;
      }
      return;
    } catch (_) {
      payload.issues.push({
        code: "invalid_format",
        format: "url",
        input: payload.value,
        inst,
        continue: !def.abort
      });
    }
  };
});
const $ZodEmoji = /* @__PURE__ */ $constructor("$ZodEmoji", (inst, def) => {
  def.pattern ?? (def.pattern = emoji());
  $ZodStringFormat.init(inst, def);
});
const $ZodNanoID = /* @__PURE__ */ $constructor("$ZodNanoID", (inst, def) => {
  def.pattern ?? (def.pattern = nanoid);
  $ZodStringFormat.init(inst, def);
});
const $ZodCUID = /* @__PURE__ */ $constructor("$ZodCUID", (inst, def) => {
  def.pattern ?? (def.pattern = cuid);
  $ZodStringFormat.init(inst, def);
});
const $ZodCUID2 = /* @__PURE__ */ $constructor("$ZodCUID2", (inst, def) => {
  def.pattern ?? (def.pattern = cuid2);
  $ZodStringFormat.init(inst, def);
});
const $ZodULID = /* @__PURE__ */ $constructor("$ZodULID", (inst, def) => {
  def.pattern ?? (def.pattern = ulid);
  $ZodStringFormat.init(inst, def);
});
const $ZodXID = /* @__PURE__ */ $constructor("$ZodXID", (inst, def) => {
  def.pattern ?? (def.pattern = xid);
  $ZodStringFormat.init(inst, def);
});
const $ZodKSUID = /* @__PURE__ */ $constructor("$ZodKSUID", (inst, def) => {
  def.pattern ?? (def.pattern = ksuid);
  $ZodStringFormat.init(inst, def);
});
const $ZodISODateTime = /* @__PURE__ */ $constructor("$ZodISODateTime", (inst, def) => {
  def.pattern ?? (def.pattern = datetime$1(def));
  $ZodStringFormat.init(inst, def);
});
const $ZodISODate = /* @__PURE__ */ $constructor("$ZodISODate", (inst, def) => {
  def.pattern ?? (def.pattern = date$1);
  $ZodStringFormat.init(inst, def);
});
const $ZodISOTime = /* @__PURE__ */ $constructor("$ZodISOTime", (inst, def) => {
  def.pattern ?? (def.pattern = time$1(def));
  $ZodStringFormat.init(inst, def);
});
const $ZodISODuration = /* @__PURE__ */ $constructor("$ZodISODuration", (inst, def) => {
  def.pattern ?? (def.pattern = duration$1);
  $ZodStringFormat.init(inst, def);
});
const $ZodIPv4 = /* @__PURE__ */ $constructor("$ZodIPv4", (inst, def) => {
  def.pattern ?? (def.pattern = ipv4);
  $ZodStringFormat.init(inst, def);
  inst._zod.bag.format = `ipv4`;
});
const $ZodIPv6 = /* @__PURE__ */ $constructor("$ZodIPv6", (inst, def) => {
  def.pattern ?? (def.pattern = ipv6);
  $ZodStringFormat.init(inst, def);
  inst._zod.bag.format = `ipv6`;
  inst._zod.check = (payload) => {
    try {
      new URL(`http://[${payload.value}]`);
    } catch {
      payload.issues.push({
        code: "invalid_format",
        format: "ipv6",
        input: payload.value,
        inst,
        continue: !def.abort
      });
    }
  };
});
const $ZodCIDRv4 = /* @__PURE__ */ $constructor("$ZodCIDRv4", (inst, def) => {
  def.pattern ?? (def.pattern = cidrv4);
  $ZodStringFormat.init(inst, def);
});
const $ZodCIDRv6 = /* @__PURE__ */ $constructor("$ZodCIDRv6", (inst, def) => {
  def.pattern ?? (def.pattern = cidrv6);
  $ZodStringFormat.init(inst, def);
  inst._zod.check = (payload) => {
    const parts = payload.value.split("/");
    try {
      if (parts.length !== 2)
        throw new Error();
      const [address, prefix] = parts;
      if (!prefix)
        throw new Error();
      const prefixNum = Number(prefix);
      if (`${prefixNum}` !== prefix)
        throw new Error();
      if (prefixNum < 0 || prefixNum > 128)
        throw new Error();
      new URL(`http://[${address}]`);
    } catch {
      payload.issues.push({
        code: "invalid_format",
        format: "cidrv6",
        input: payload.value,
        inst,
        continue: !def.abort
      });
    }
  };
});
function isValidBase64(data) {
  if (data === "")
    return true;
  if (data.length % 4 !== 0)
    return false;
  try {
    atob(data);
    return true;
  } catch {
    return false;
  }
}
const $ZodBase64 = /* @__PURE__ */ $constructor("$ZodBase64", (inst, def) => {
  def.pattern ?? (def.pattern = base64);
  $ZodStringFormat.init(inst, def);
  inst._zod.bag.contentEncoding = "base64";
  inst._zod.check = (payload) => {
    if (isValidBase64(payload.value))
      return;
    payload.issues.push({
      code: "invalid_format",
      format: "base64",
      input: payload.value,
      inst,
      continue: !def.abort
    });
  };
});
function isValidBase64URL(data) {
  if (!base64url.test(data))
    return false;
  const base642 = data.replace(/[-_]/g, (c) => c === "-" ? "+" : "/");
  const padded = base642.padEnd(Math.ceil(base642.length / 4) * 4, "=");
  return isValidBase64(padded);
}
const $ZodBase64URL = /* @__PURE__ */ $constructor("$ZodBase64URL", (inst, def) => {
  def.pattern ?? (def.pattern = base64url);
  $ZodStringFormat.init(inst, def);
  inst._zod.bag.contentEncoding = "base64url";
  inst._zod.check = (payload) => {
    if (isValidBase64URL(payload.value))
      return;
    payload.issues.push({
      code: "invalid_format",
      format: "base64url",
      input: payload.value,
      inst,
      continue: !def.abort
    });
  };
});
const $ZodE164 = /* @__PURE__ */ $constructor("$ZodE164", (inst, def) => {
  def.pattern ?? (def.pattern = e164);
  $ZodStringFormat.init(inst, def);
});
function isValidJWT(token, algorithm = null) {
  try {
    const tokensParts = token.split(".");
    if (tokensParts.length !== 3)
      return false;
    const [header] = tokensParts;
    if (!header)
      return false;
    const parsedHeader = JSON.parse(atob(header));
    if ("typ" in parsedHeader && (parsedHeader == null ? void 0 : parsedHeader.typ) !== "JWT")
      return false;
    if (!parsedHeader.alg)
      return false;
    if (algorithm && (!("alg" in parsedHeader) || parsedHeader.alg !== algorithm))
      return false;
    return true;
  } catch {
    return false;
  }
}
const $ZodJWT = /* @__PURE__ */ $constructor("$ZodJWT", (inst, def) => {
  $ZodStringFormat.init(inst, def);
  inst._zod.check = (payload) => {
    if (isValidJWT(payload.value, def.alg))
      return;
    payload.issues.push({
      code: "invalid_format",
      format: "jwt",
      input: payload.value,
      inst,
      continue: !def.abort
    });
  };
});
const $ZodNumber = /* @__PURE__ */ $constructor("$ZodNumber", (inst, def) => {
  $ZodType.init(inst, def);
  inst._zod.pattern = inst._zod.bag.pattern ?? number$1;
  inst._zod.parse = (payload, _ctx) => {
    if (def.coerce)
      try {
        payload.value = Number(payload.value);
      } catch (_) {
      }
    const input = payload.value;
    if (typeof input === "number" && !Number.isNaN(input) && Number.isFinite(input)) {
      return payload;
    }
    const received = typeof input === "number" ? Number.isNaN(input) ? "NaN" : !Number.isFinite(input) ? "Infinity" : void 0 : void 0;
    payload.issues.push({
      expected: "number",
      code: "invalid_type",
      input,
      inst,
      ...received ? { received } : {}
    });
    return payload;
  };
});
const $ZodNumberFormat = /* @__PURE__ */ $constructor("$ZodNumberFormat", (inst, def) => {
  $ZodCheckNumberFormat.init(inst, def);
  $ZodNumber.init(inst, def);
});
const $ZodBoolean = /* @__PURE__ */ $constructor("$ZodBoolean", (inst, def) => {
  $ZodType.init(inst, def);
  inst._zod.pattern = boolean$1;
  inst._zod.parse = (payload, _ctx) => {
    if (def.coerce)
      try {
        payload.value = Boolean(payload.value);
      } catch (_) {
      }
    const input = payload.value;
    if (typeof input === "boolean")
      return payload;
    payload.issues.push({
      expected: "boolean",
      code: "invalid_type",
      input,
      inst
    });
    return payload;
  };
});
const $ZodUnknown = /* @__PURE__ */ $constructor("$ZodUnknown", (inst, def) => {
  $ZodType.init(inst, def);
  inst._zod.parse = (payload) => payload;
});
const $ZodNever = /* @__PURE__ */ $constructor("$ZodNever", (inst, def) => {
  $ZodType.init(inst, def);
  inst._zod.parse = (payload, _ctx) => {
    payload.issues.push({
      expected: "never",
      code: "invalid_type",
      input: payload.value,
      inst
    });
    return payload;
  };
});
function handleArrayResult(result, final, index) {
  if (result.issues.length) {
    final.issues.push(...prefixIssues(index, result.issues));
  }
  final.value[index] = result.value;
}
const $ZodArray = /* @__PURE__ */ $constructor("$ZodArray", (inst, def) => {
  $ZodType.init(inst, def);
  inst._zod.parse = (payload, ctx) => {
    const input = payload.value;
    if (!Array.isArray(input)) {
      payload.issues.push({
        expected: "array",
        code: "invalid_type",
        input,
        inst
      });
      return payload;
    }
    payload.value = Array(input.length);
    const proms = [];
    for (let i = 0; i < input.length; i++) {
      const item = input[i];
      const result = def.element._zod.run({
        value: item,
        issues: []
      }, ctx);
      if (result instanceof Promise) {
        proms.push(result.then((result2) => handleArrayResult(result2, payload, i)));
      } else {
        handleArrayResult(result, payload, i);
      }
    }
    if (proms.length) {
      return Promise.all(proms).then(() => payload);
    }
    return payload;
  };
});
function handlePropertyResult(result, final, key, input, isOptionalOut) {
  if (result.issues.length) {
    if (isOptionalOut && !(key in input)) {
      return;
    }
    final.issues.push(...prefixIssues(key, result.issues));
  }
  if (result.value === void 0) {
    if (key in input) {
      final.value[key] = void 0;
    }
  } else {
    final.value[key] = result.value;
  }
}
function normalizeDef(def) {
  var _a3, _b, _c, _d;
  const keys = Object.keys(def.shape);
  for (const k of keys) {
    if (!((_d = (_c = (_b = (_a3 = def.shape) == null ? void 0 : _a3[k]) == null ? void 0 : _b._zod) == null ? void 0 : _c.traits) == null ? void 0 : _d.has("$ZodType"))) {
      throw new Error(`Invalid element at key "${k}": expected a Zod schema`);
    }
  }
  const okeys = optionalKeys(def.shape);
  return {
    ...def,
    keys,
    keySet: new Set(keys),
    numKeys: keys.length,
    optionalKeys: new Set(okeys)
  };
}
function handleCatchall(proms, input, payload, ctx, def, inst) {
  const unrecognized = [];
  const keySet = def.keySet;
  const _catchall = def.catchall._zod;
  const t = _catchall.def.type;
  const isOptionalOut = _catchall.optout === "optional";
  for (const key in input) {
    if (keySet.has(key))
      continue;
    if (t === "never") {
      unrecognized.push(key);
      continue;
    }
    const r = _catchall.run({ value: input[key], issues: [] }, ctx);
    if (r instanceof Promise) {
      proms.push(r.then((r2) => handlePropertyResult(r2, payload, key, input, isOptionalOut)));
    } else {
      handlePropertyResult(r, payload, key, input, isOptionalOut);
    }
  }
  if (unrecognized.length) {
    payload.issues.push({
      code: "unrecognized_keys",
      keys: unrecognized,
      input,
      inst
    });
  }
  if (!proms.length)
    return payload;
  return Promise.all(proms).then(() => {
    return payload;
  });
}
const $ZodObject = /* @__PURE__ */ $constructor("$ZodObject", (inst, def) => {
  $ZodType.init(inst, def);
  const desc = Object.getOwnPropertyDescriptor(def, "shape");
  if (!(desc == null ? void 0 : desc.get)) {
    const sh = def.shape;
    Object.defineProperty(def, "shape", {
      get: () => {
        const newSh = { ...sh };
        Object.defineProperty(def, "shape", {
          value: newSh
        });
        return newSh;
      }
    });
  }
  const _normalized = cached(() => normalizeDef(def));
  defineLazy(inst._zod, "propValues", () => {
    const shape = def.shape;
    const propValues = {};
    for (const key in shape) {
      const field = shape[key]._zod;
      if (field.values) {
        propValues[key] ?? (propValues[key] = /* @__PURE__ */ new Set());
        for (const v of field.values)
          propValues[key].add(v);
      }
    }
    return propValues;
  });
  const isObject$1 = isObject;
  const catchall = def.catchall;
  let value;
  inst._zod.parse = (payload, ctx) => {
    value ?? (value = _normalized.value);
    const input = payload.value;
    if (!isObject$1(input)) {
      payload.issues.push({
        expected: "object",
        code: "invalid_type",
        input,
        inst
      });
      return payload;
    }
    payload.value = {};
    const proms = [];
    const shape = value.shape;
    for (const key of value.keys) {
      const el = shape[key];
      const isOptionalOut = el._zod.optout === "optional";
      const r = el._zod.run({ value: input[key], issues: [] }, ctx);
      if (r instanceof Promise) {
        proms.push(r.then((r2) => handlePropertyResult(r2, payload, key, input, isOptionalOut)));
      } else {
        handlePropertyResult(r, payload, key, input, isOptionalOut);
      }
    }
    if (!catchall) {
      return proms.length ? Promise.all(proms).then(() => payload) : payload;
    }
    return handleCatchall(proms, input, payload, ctx, _normalized.value, inst);
  };
});
const $ZodObjectJIT = /* @__PURE__ */ $constructor("$ZodObjectJIT", (inst, def) => {
  $ZodObject.init(inst, def);
  const superParse = inst._zod.parse;
  const _normalized = cached(() => normalizeDef(def));
  const generateFastpass = (shape) => {
    var _a3;
    const doc = new Doc(["shape", "payload", "ctx"]);
    const normalized = _normalized.value;
    const parseStr = (key) => {
      const k = esc(key);
      return `shape[${k}]._zod.run({ value: input[${k}], issues: [] }, ctx)`;
    };
    doc.write(`const input = payload.value;`);
    const ids = /* @__PURE__ */ Object.create(null);
    let counter = 0;
    for (const key of normalized.keys) {
      ids[key] = `key_${counter++}`;
    }
    doc.write(`const newResult = {};`);
    for (const key of normalized.keys) {
      const id = ids[key];
      const k = esc(key);
      const schema = shape[key];
      const isOptionalOut = ((_a3 = schema == null ? void 0 : schema._zod) == null ? void 0 : _a3.optout) === "optional";
      doc.write(`const ${id} = ${parseStr(key)};`);
      if (isOptionalOut) {
        doc.write(`
        if (${id}.issues.length) {
          if (${k} in input) {
            payload.issues = payload.issues.concat(${id}.issues.map(iss => ({
              ...iss,
              path: iss.path ? [${k}, ...iss.path] : [${k}]
            })));
          }
        }
        
        if (${id}.value === undefined) {
          if (${k} in input) {
            newResult[${k}] = undefined;
          }
        } else {
          newResult[${k}] = ${id}.value;
        }
        
      `);
      } else {
        doc.write(`
        if (${id}.issues.length) {
          payload.issues = payload.issues.concat(${id}.issues.map(iss => ({
            ...iss,
            path: iss.path ? [${k}, ...iss.path] : [${k}]
          })));
        }
        
        if (${id}.value === undefined) {
          if (${k} in input) {
            newResult[${k}] = undefined;
          }
        } else {
          newResult[${k}] = ${id}.value;
        }
        
      `);
      }
    }
    doc.write(`payload.value = newResult;`);
    doc.write(`return payload;`);
    const fn = doc.compile();
    return (payload, ctx) => fn(shape, payload, ctx);
  };
  let fastpass;
  const isObject$1 = isObject;
  const jit = !globalConfig.jitless;
  const allowsEval$1 = allowsEval;
  const fastEnabled = jit && allowsEval$1.value;
  const catchall = def.catchall;
  let value;
  inst._zod.parse = (payload, ctx) => {
    value ?? (value = _normalized.value);
    const input = payload.value;
    if (!isObject$1(input)) {
      payload.issues.push({
        expected: "object",
        code: "invalid_type",
        input,
        inst
      });
      return payload;
    }
    if (jit && fastEnabled && (ctx == null ? void 0 : ctx.async) === false && ctx.jitless !== true) {
      if (!fastpass)
        fastpass = generateFastpass(def.shape);
      payload = fastpass(payload, ctx);
      if (!catchall)
        return payload;
      return handleCatchall([], input, payload, ctx, value, inst);
    }
    return superParse(payload, ctx);
  };
});
function handleUnionResults(results, final, inst, ctx) {
  for (const result of results) {
    if (result.issues.length === 0) {
      final.value = result.value;
      return final;
    }
  }
  const nonaborted = results.filter((r) => !aborted(r));
  if (nonaborted.length === 1) {
    final.value = nonaborted[0].value;
    return nonaborted[0];
  }
  final.issues.push({
    code: "invalid_union",
    input: final.value,
    inst,
    errors: results.map((result) => result.issues.map((iss) => finalizeIssue(iss, ctx, config())))
  });
  return final;
}
const $ZodUnion = /* @__PURE__ */ $constructor("$ZodUnion", (inst, def) => {
  $ZodType.init(inst, def);
  defineLazy(inst._zod, "optin", () => def.options.some((o) => o._zod.optin === "optional") ? "optional" : void 0);
  defineLazy(inst._zod, "optout", () => def.options.some((o) => o._zod.optout === "optional") ? "optional" : void 0);
  defineLazy(inst._zod, "values", () => {
    if (def.options.every((o) => o._zod.values)) {
      return new Set(def.options.flatMap((option) => Array.from(option._zod.values)));
    }
    return void 0;
  });
  defineLazy(inst._zod, "pattern", () => {
    if (def.options.every((o) => o._zod.pattern)) {
      const patterns = def.options.map((o) => o._zod.pattern);
      return new RegExp(`^(${patterns.map((p) => cleanRegex(p.source)).join("|")})$`);
    }
    return void 0;
  });
  const single = def.options.length === 1;
  const first = def.options[0]._zod.run;
  inst._zod.parse = (payload, ctx) => {
    if (single) {
      return first(payload, ctx);
    }
    let async = false;
    const results = [];
    for (const option of def.options) {
      const result = option._zod.run({
        value: payload.value,
        issues: []
      }, ctx);
      if (result instanceof Promise) {
        results.push(result);
        async = true;
      } else {
        if (result.issues.length === 0)
          return result;
        results.push(result);
      }
    }
    if (!async)
      return handleUnionResults(results, payload, inst, ctx);
    return Promise.all(results).then((results2) => {
      return handleUnionResults(results2, payload, inst, ctx);
    });
  };
});
const $ZodDiscriminatedUnion = /* @__PURE__ */ $constructor("$ZodDiscriminatedUnion", (inst, def) => {
  def.inclusive = false;
  $ZodUnion.init(inst, def);
  const _super = inst._zod.parse;
  defineLazy(inst._zod, "propValues", () => {
    const propValues = {};
    for (const option of def.options) {
      const pv = option._zod.propValues;
      if (!pv || Object.keys(pv).length === 0)
        throw new Error(`Invalid discriminated union option at index "${def.options.indexOf(option)}"`);
      for (const [k, v] of Object.entries(pv)) {
        if (!propValues[k])
          propValues[k] = /* @__PURE__ */ new Set();
        for (const val of v) {
          propValues[k].add(val);
        }
      }
    }
    return propValues;
  });
  const disc = cached(() => {
    var _a3;
    const opts = def.options;
    const map = /* @__PURE__ */ new Map();
    for (const o of opts) {
      const values = (_a3 = o._zod.propValues) == null ? void 0 : _a3[def.discriminator];
      if (!values || values.size === 0)
        throw new Error(`Invalid discriminated union option at index "${def.options.indexOf(o)}"`);
      for (const v of values) {
        if (map.has(v)) {
          throw new Error(`Duplicate discriminator value "${String(v)}"`);
        }
        map.set(v, o);
      }
    }
    return map;
  });
  inst._zod.parse = (payload, ctx) => {
    const input = payload.value;
    if (!isObject(input)) {
      payload.issues.push({
        code: "invalid_type",
        expected: "object",
        input,
        inst
      });
      return payload;
    }
    const opt = disc.value.get(input == null ? void 0 : input[def.discriminator]);
    if (opt) {
      return opt._zod.run(payload, ctx);
    }
    if (def.unionFallback) {
      return _super(payload, ctx);
    }
    payload.issues.push({
      code: "invalid_union",
      errors: [],
      note: "No matching discriminator",
      discriminator: def.discriminator,
      input,
      path: [def.discriminator],
      inst
    });
    return payload;
  };
});
const $ZodIntersection = /* @__PURE__ */ $constructor("$ZodIntersection", (inst, def) => {
  $ZodType.init(inst, def);
  inst._zod.parse = (payload, ctx) => {
    const input = payload.value;
    const left = def.left._zod.run({ value: input, issues: [] }, ctx);
    const right = def.right._zod.run({ value: input, issues: [] }, ctx);
    const async = left instanceof Promise || right instanceof Promise;
    if (async) {
      return Promise.all([left, right]).then(([left2, right2]) => {
        return handleIntersectionResults(payload, left2, right2);
      });
    }
    return handleIntersectionResults(payload, left, right);
  };
});
function mergeValues(a, b) {
  if (a === b) {
    return { valid: true, data: a };
  }
  if (a instanceof Date && b instanceof Date && +a === +b) {
    return { valid: true, data: a };
  }
  if (isPlainObject(a) && isPlainObject(b)) {
    const bKeys = Object.keys(b);
    const sharedKeys = Object.keys(a).filter((key) => bKeys.indexOf(key) !== -1);
    const newObj = { ...a, ...b };
    for (const key of sharedKeys) {
      const sharedValue = mergeValues(a[key], b[key]);
      if (!sharedValue.valid) {
        return {
          valid: false,
          mergeErrorPath: [key, ...sharedValue.mergeErrorPath]
        };
      }
      newObj[key] = sharedValue.data;
    }
    return { valid: true, data: newObj };
  }
  if (Array.isArray(a) && Array.isArray(b)) {
    if (a.length !== b.length) {
      return { valid: false, mergeErrorPath: [] };
    }
    const newArray = [];
    for (let index = 0; index < a.length; index++) {
      const itemA = a[index];
      const itemB = b[index];
      const sharedValue = mergeValues(itemA, itemB);
      if (!sharedValue.valid) {
        return {
          valid: false,
          mergeErrorPath: [index, ...sharedValue.mergeErrorPath]
        };
      }
      newArray.push(sharedValue.data);
    }
    return { valid: true, data: newArray };
  }
  return { valid: false, mergeErrorPath: [] };
}
function handleIntersectionResults(result, left, right) {
  const unrecKeys = /* @__PURE__ */ new Map();
  let unrecIssue;
  for (const iss of left.issues) {
    if (iss.code === "unrecognized_keys") {
      unrecIssue ?? (unrecIssue = iss);
      for (const k of iss.keys) {
        if (!unrecKeys.has(k))
          unrecKeys.set(k, {});
        unrecKeys.get(k).l = true;
      }
    } else {
      result.issues.push(iss);
    }
  }
  for (const iss of right.issues) {
    if (iss.code === "unrecognized_keys") {
      for (const k of iss.keys) {
        if (!unrecKeys.has(k))
          unrecKeys.set(k, {});
        unrecKeys.get(k).r = true;
      }
    } else {
      result.issues.push(iss);
    }
  }
  const bothKeys = [...unrecKeys].filter(([, f]) => f.l && f.r).map(([k]) => k);
  if (bothKeys.length && unrecIssue) {
    result.issues.push({ ...unrecIssue, keys: bothKeys });
  }
  if (aborted(result))
    return result;
  const merged = mergeValues(left.value, right.value);
  if (!merged.valid) {
    throw new Error(`Unmergable intersection. Error path: ${JSON.stringify(merged.mergeErrorPath)}`);
  }
  result.value = merged.data;
  return result;
}
const $ZodTuple = /* @__PURE__ */ $constructor("$ZodTuple", (inst, def) => {
  $ZodType.init(inst, def);
  const items = def.items;
  inst._zod.parse = (payload, ctx) => {
    const input = payload.value;
    if (!Array.isArray(input)) {
      payload.issues.push({
        input,
        inst,
        expected: "tuple",
        code: "invalid_type"
      });
      return payload;
    }
    payload.value = [];
    const proms = [];
    const reversedIndex = [...items].reverse().findIndex((item) => item._zod.optin !== "optional");
    const optStart = reversedIndex === -1 ? 0 : items.length - reversedIndex;
    if (!def.rest) {
      const tooBig = input.length > items.length;
      const tooSmall = input.length < optStart - 1;
      if (tooBig || tooSmall) {
        payload.issues.push({
          ...tooBig ? { code: "too_big", maximum: items.length, inclusive: true } : { code: "too_small", minimum: items.length },
          input,
          inst,
          origin: "array"
        });
        return payload;
      }
    }
    let i = -1;
    for (const item of items) {
      i++;
      if (i >= input.length) {
        if (i >= optStart)
          continue;
      }
      const result = item._zod.run({
        value: input[i],
        issues: []
      }, ctx);
      if (result instanceof Promise) {
        proms.push(result.then((result2) => handleTupleResult(result2, payload, i)));
      } else {
        handleTupleResult(result, payload, i);
      }
    }
    if (def.rest) {
      const rest = input.slice(items.length);
      for (const el of rest) {
        i++;
        const result = def.rest._zod.run({
          value: el,
          issues: []
        }, ctx);
        if (result instanceof Promise) {
          proms.push(result.then((result2) => handleTupleResult(result2, payload, i)));
        } else {
          handleTupleResult(result, payload, i);
        }
      }
    }
    if (proms.length)
      return Promise.all(proms).then(() => payload);
    return payload;
  };
});
function handleTupleResult(result, final, index) {
  if (result.issues.length) {
    final.issues.push(...prefixIssues(index, result.issues));
  }
  final.value[index] = result.value;
}
const $ZodRecord = /* @__PURE__ */ $constructor("$ZodRecord", (inst, def) => {
  $ZodType.init(inst, def);
  inst._zod.parse = (payload, ctx) => {
    const input = payload.value;
    if (!isPlainObject(input)) {
      payload.issues.push({
        expected: "record",
        code: "invalid_type",
        input,
        inst
      });
      return payload;
    }
    const proms = [];
    const values = def.keyType._zod.values;
    if (values) {
      payload.value = {};
      const recordKeys = /* @__PURE__ */ new Set();
      for (const key of values) {
        if (typeof key === "string" || typeof key === "number" || typeof key === "symbol") {
          recordKeys.add(typeof key === "number" ? key.toString() : key);
          const result = def.valueType._zod.run({ value: input[key], issues: [] }, ctx);
          if (result instanceof Promise) {
            proms.push(result.then((result2) => {
              if (result2.issues.length) {
                payload.issues.push(...prefixIssues(key, result2.issues));
              }
              payload.value[key] = result2.value;
            }));
          } else {
            if (result.issues.length) {
              payload.issues.push(...prefixIssues(key, result.issues));
            }
            payload.value[key] = result.value;
          }
        }
      }
      let unrecognized;
      for (const key in input) {
        if (!recordKeys.has(key)) {
          unrecognized = unrecognized ?? [];
          unrecognized.push(key);
        }
      }
      if (unrecognized && unrecognized.length > 0) {
        payload.issues.push({
          code: "unrecognized_keys",
          input,
          inst,
          keys: unrecognized
        });
      }
    } else {
      payload.value = {};
      for (const key of Reflect.ownKeys(input)) {
        if (key === "__proto__")
          continue;
        let keyResult = def.keyType._zod.run({ value: key, issues: [] }, ctx);
        if (keyResult instanceof Promise) {
          throw new Error("Async schemas not supported in object keys currently");
        }
        const checkNumericKey = typeof key === "string" && number$1.test(key) && keyResult.issues.length;
        if (checkNumericKey) {
          const retryResult = def.keyType._zod.run({ value: Number(key), issues: [] }, ctx);
          if (retryResult instanceof Promise) {
            throw new Error("Async schemas not supported in object keys currently");
          }
          if (retryResult.issues.length === 0) {
            keyResult = retryResult;
          }
        }
        if (keyResult.issues.length) {
          if (def.mode === "loose") {
            payload.value[key] = input[key];
          } else {
            payload.issues.push({
              code: "invalid_key",
              origin: "record",
              issues: keyResult.issues.map((iss) => finalizeIssue(iss, ctx, config())),
              input: key,
              path: [key],
              inst
            });
          }
          continue;
        }
        const result = def.valueType._zod.run({ value: input[key], issues: [] }, ctx);
        if (result instanceof Promise) {
          proms.push(result.then((result2) => {
            if (result2.issues.length) {
              payload.issues.push(...prefixIssues(key, result2.issues));
            }
            payload.value[keyResult.value] = result2.value;
          }));
        } else {
          if (result.issues.length) {
            payload.issues.push(...prefixIssues(key, result.issues));
          }
          payload.value[keyResult.value] = result.value;
        }
      }
    }
    if (proms.length) {
      return Promise.all(proms).then(() => payload);
    }
    return payload;
  };
});
const $ZodEnum = /* @__PURE__ */ $constructor("$ZodEnum", (inst, def) => {
  $ZodType.init(inst, def);
  const values = getEnumValues(def.entries);
  const valuesSet = new Set(values);
  inst._zod.values = valuesSet;
  inst._zod.pattern = new RegExp(`^(${values.filter((k) => propertyKeyTypes.has(typeof k)).map((o) => typeof o === "string" ? escapeRegex(o) : o.toString()).join("|")})$`);
  inst._zod.parse = (payload, _ctx) => {
    const input = payload.value;
    if (valuesSet.has(input)) {
      return payload;
    }
    payload.issues.push({
      code: "invalid_value",
      values,
      input,
      inst
    });
    return payload;
  };
});
const $ZodLiteral = /* @__PURE__ */ $constructor("$ZodLiteral", (inst, def) => {
  $ZodType.init(inst, def);
  if (def.values.length === 0) {
    throw new Error("Cannot create literal schema with no valid values");
  }
  const values = new Set(def.values);
  inst._zod.values = values;
  inst._zod.pattern = new RegExp(`^(${def.values.map((o) => typeof o === "string" ? escapeRegex(o) : o ? escapeRegex(o.toString()) : String(o)).join("|")})$`);
  inst._zod.parse = (payload, _ctx) => {
    const input = payload.value;
    if (values.has(input)) {
      return payload;
    }
    payload.issues.push({
      code: "invalid_value",
      values: def.values,
      input,
      inst
    });
    return payload;
  };
});
const $ZodTransform = /* @__PURE__ */ $constructor("$ZodTransform", (inst, def) => {
  $ZodType.init(inst, def);
  inst._zod.parse = (payload, ctx) => {
    if (ctx.direction === "backward") {
      throw new $ZodEncodeError(inst.constructor.name);
    }
    const _out = def.transform(payload.value, payload);
    if (ctx.async) {
      const output = _out instanceof Promise ? _out : Promise.resolve(_out);
      return output.then((output2) => {
        payload.value = output2;
        return payload;
      });
    }
    if (_out instanceof Promise) {
      throw new $ZodAsyncError();
    }
    payload.value = _out;
    return payload;
  };
});
function handleOptionalResult(result, input) {
  if (result.issues.length && input === void 0) {
    return { issues: [], value: void 0 };
  }
  return result;
}
const $ZodOptional = /* @__PURE__ */ $constructor("$ZodOptional", (inst, def) => {
  $ZodType.init(inst, def);
  inst._zod.optin = "optional";
  inst._zod.optout = "optional";
  defineLazy(inst._zod, "values", () => {
    return def.innerType._zod.values ? /* @__PURE__ */ new Set([...def.innerType._zod.values, void 0]) : void 0;
  });
  defineLazy(inst._zod, "pattern", () => {
    const pattern = def.innerType._zod.pattern;
    return pattern ? new RegExp(`^(${cleanRegex(pattern.source)})?$`) : void 0;
  });
  inst._zod.parse = (payload, ctx) => {
    if (def.innerType._zod.optin === "optional") {
      const result = def.innerType._zod.run(payload, ctx);
      if (result instanceof Promise)
        return result.then((r) => handleOptionalResult(r, payload.value));
      return handleOptionalResult(result, payload.value);
    }
    if (payload.value === void 0) {
      return payload;
    }
    return def.innerType._zod.run(payload, ctx);
  };
});
const $ZodExactOptional = /* @__PURE__ */ $constructor("$ZodExactOptional", (inst, def) => {
  $ZodOptional.init(inst, def);
  defineLazy(inst._zod, "values", () => def.innerType._zod.values);
  defineLazy(inst._zod, "pattern", () => def.innerType._zod.pattern);
  inst._zod.parse = (payload, ctx) => {
    return def.innerType._zod.run(payload, ctx);
  };
});
const $ZodNullable = /* @__PURE__ */ $constructor("$ZodNullable", (inst, def) => {
  $ZodType.init(inst, def);
  defineLazy(inst._zod, "optin", () => def.innerType._zod.optin);
  defineLazy(inst._zod, "optout", () => def.innerType._zod.optout);
  defineLazy(inst._zod, "pattern", () => {
    const pattern = def.innerType._zod.pattern;
    return pattern ? new RegExp(`^(${cleanRegex(pattern.source)}|null)$`) : void 0;
  });
  defineLazy(inst._zod, "values", () => {
    return def.innerType._zod.values ? /* @__PURE__ */ new Set([...def.innerType._zod.values, null]) : void 0;
  });
  inst._zod.parse = (payload, ctx) => {
    if (payload.value === null)
      return payload;
    return def.innerType._zod.run(payload, ctx);
  };
});
const $ZodDefault = /* @__PURE__ */ $constructor("$ZodDefault", (inst, def) => {
  $ZodType.init(inst, def);
  inst._zod.optin = "optional";
  defineLazy(inst._zod, "values", () => def.innerType._zod.values);
  inst._zod.parse = (payload, ctx) => {
    if (ctx.direction === "backward") {
      return def.innerType._zod.run(payload, ctx);
    }
    if (payload.value === void 0) {
      payload.value = def.defaultValue;
      return payload;
    }
    const result = def.innerType._zod.run(payload, ctx);
    if (result instanceof Promise) {
      return result.then((result2) => handleDefaultResult(result2, def));
    }
    return handleDefaultResult(result, def);
  };
});
function handleDefaultResult(payload, def) {
  if (payload.value === void 0) {
    payload.value = def.defaultValue;
  }
  return payload;
}
const $ZodPrefault = /* @__PURE__ */ $constructor("$ZodPrefault", (inst, def) => {
  $ZodType.init(inst, def);
  inst._zod.optin = "optional";
  defineLazy(inst._zod, "values", () => def.innerType._zod.values);
  inst._zod.parse = (payload, ctx) => {
    if (ctx.direction === "backward") {
      return def.innerType._zod.run(payload, ctx);
    }
    if (payload.value === void 0) {
      payload.value = def.defaultValue;
    }
    return def.innerType._zod.run(payload, ctx);
  };
});
const $ZodNonOptional = /* @__PURE__ */ $constructor("$ZodNonOptional", (inst, def) => {
  $ZodType.init(inst, def);
  defineLazy(inst._zod, "values", () => {
    const v = def.innerType._zod.values;
    return v ? new Set([...v].filter((x) => x !== void 0)) : void 0;
  });
  inst._zod.parse = (payload, ctx) => {
    const result = def.innerType._zod.run(payload, ctx);
    if (result instanceof Promise) {
      return result.then((result2) => handleNonOptionalResult(result2, inst));
    }
    return handleNonOptionalResult(result, inst);
  };
});
function handleNonOptionalResult(payload, inst) {
  if (!payload.issues.length && payload.value === void 0) {
    payload.issues.push({
      code: "invalid_type",
      expected: "nonoptional",
      input: payload.value,
      inst
    });
  }
  return payload;
}
const $ZodCatch = /* @__PURE__ */ $constructor("$ZodCatch", (inst, def) => {
  $ZodType.init(inst, def);
  defineLazy(inst._zod, "optin", () => def.innerType._zod.optin);
  defineLazy(inst._zod, "optout", () => def.innerType._zod.optout);
  defineLazy(inst._zod, "values", () => def.innerType._zod.values);
  inst._zod.parse = (payload, ctx) => {
    if (ctx.direction === "backward") {
      return def.innerType._zod.run(payload, ctx);
    }
    const result = def.innerType._zod.run(payload, ctx);
    if (result instanceof Promise) {
      return result.then((result2) => {
        payload.value = result2.value;
        if (result2.issues.length) {
          payload.value = def.catchValue({
            ...payload,
            error: {
              issues: result2.issues.map((iss) => finalizeIssue(iss, ctx, config()))
            },
            input: payload.value
          });
          payload.issues = [];
        }
        return payload;
      });
    }
    payload.value = result.value;
    if (result.issues.length) {
      payload.value = def.catchValue({
        ...payload,
        error: {
          issues: result.issues.map((iss) => finalizeIssue(iss, ctx, config()))
        },
        input: payload.value
      });
      payload.issues = [];
    }
    return payload;
  };
});
const $ZodPipe = /* @__PURE__ */ $constructor("$ZodPipe", (inst, def) => {
  $ZodType.init(inst, def);
  defineLazy(inst._zod, "values", () => def.in._zod.values);
  defineLazy(inst._zod, "optin", () => def.in._zod.optin);
  defineLazy(inst._zod, "optout", () => def.out._zod.optout);
  defineLazy(inst._zod, "propValues", () => def.in._zod.propValues);
  inst._zod.parse = (payload, ctx) => {
    if (ctx.direction === "backward") {
      const right = def.out._zod.run(payload, ctx);
      if (right instanceof Promise) {
        return right.then((right2) => handlePipeResult(right2, def.in, ctx));
      }
      return handlePipeResult(right, def.in, ctx);
    }
    const left = def.in._zod.run(payload, ctx);
    if (left instanceof Promise) {
      return left.then((left2) => handlePipeResult(left2, def.out, ctx));
    }
    return handlePipeResult(left, def.out, ctx);
  };
});
function handlePipeResult(left, next, ctx) {
  if (left.issues.length) {
    left.aborted = true;
    return left;
  }
  return next._zod.run({ value: left.value, issues: left.issues }, ctx);
}
const $ZodReadonly = /* @__PURE__ */ $constructor("$ZodReadonly", (inst, def) => {
  $ZodType.init(inst, def);
  defineLazy(inst._zod, "propValues", () => def.innerType._zod.propValues);
  defineLazy(inst._zod, "values", () => def.innerType._zod.values);
  defineLazy(inst._zod, "optin", () => {
    var _a3, _b;
    return (_b = (_a3 = def.innerType) == null ? void 0 : _a3._zod) == null ? void 0 : _b.optin;
  });
  defineLazy(inst._zod, "optout", () => {
    var _a3, _b;
    return (_b = (_a3 = def.innerType) == null ? void 0 : _a3._zod) == null ? void 0 : _b.optout;
  });
  inst._zod.parse = (payload, ctx) => {
    if (ctx.direction === "backward") {
      return def.innerType._zod.run(payload, ctx);
    }
    const result = def.innerType._zod.run(payload, ctx);
    if (result instanceof Promise) {
      return result.then(handleReadonlyResult);
    }
    return handleReadonlyResult(result);
  };
});
function handleReadonlyResult(payload) {
  payload.value = Object.freeze(payload.value);
  return payload;
}
const $ZodLazy = /* @__PURE__ */ $constructor("$ZodLazy", (inst, def) => {
  $ZodType.init(inst, def);
  defineLazy(inst._zod, "innerType", () => def.getter());
  defineLazy(inst._zod, "pattern", () => {
    var _a3, _b;
    return (_b = (_a3 = inst._zod.innerType) == null ? void 0 : _a3._zod) == null ? void 0 : _b.pattern;
  });
  defineLazy(inst._zod, "propValues", () => {
    var _a3, _b;
    return (_b = (_a3 = inst._zod.innerType) == null ? void 0 : _a3._zod) == null ? void 0 : _b.propValues;
  });
  defineLazy(inst._zod, "optin", () => {
    var _a3, _b;
    return ((_b = (_a3 = inst._zod.innerType) == null ? void 0 : _a3._zod) == null ? void 0 : _b.optin) ?? void 0;
  });
  defineLazy(inst._zod, "optout", () => {
    var _a3, _b;
    return ((_b = (_a3 = inst._zod.innerType) == null ? void 0 : _a3._zod) == null ? void 0 : _b.optout) ?? void 0;
  });
  inst._zod.parse = (payload, ctx) => {
    const inner = inst._zod.innerType;
    return inner._zod.run(payload, ctx);
  };
});
const $ZodCustom = /* @__PURE__ */ $constructor("$ZodCustom", (inst, def) => {
  $ZodCheck.init(inst, def);
  $ZodType.init(inst, def);
  inst._zod.parse = (payload, _) => {
    return payload;
  };
  inst._zod.check = (payload) => {
    const input = payload.value;
    const r = def.fn(input);
    if (r instanceof Promise) {
      return r.then((r2) => handleRefineResult(r2, payload, input, inst));
    }
    handleRefineResult(r, payload, input, inst);
    return;
  };
});
function handleRefineResult(result, payload, input, inst) {
  if (!result) {
    const _iss = {
      code: "custom",
      input,
      inst,
      // incorporates params.error into issue reporting
      path: [...inst._zod.def.path ?? []],
      // incorporates params.error into issue reporting
      continue: !inst._zod.def.abort
      // params: inst._zod.def.params,
    };
    if (inst._zod.def.params)
      _iss.params = inst._zod.def.params;
    payload.issues.push(issue(_iss));
  }
}
var _a;
class $ZodRegistry {
  constructor() {
    this._map = /* @__PURE__ */ new WeakMap();
    this._idmap = /* @__PURE__ */ new Map();
  }
  add(schema, ..._meta) {
    const meta = _meta[0];
    this._map.set(schema, meta);
    if (meta && typeof meta === "object" && "id" in meta) {
      this._idmap.set(meta.id, schema);
    }
    return this;
  }
  clear() {
    this._map = /* @__PURE__ */ new WeakMap();
    this._idmap = /* @__PURE__ */ new Map();
    return this;
  }
  remove(schema) {
    const meta = this._map.get(schema);
    if (meta && typeof meta === "object" && "id" in meta) {
      this._idmap.delete(meta.id);
    }
    this._map.delete(schema);
    return this;
  }
  get(schema) {
    const p = schema._zod.parent;
    if (p) {
      const pm = { ...this.get(p) ?? {} };
      delete pm.id;
      const f = { ...pm, ...this._map.get(schema) };
      return Object.keys(f).length ? f : void 0;
    }
    return this._map.get(schema);
  }
  has(schema) {
    return this._map.has(schema);
  }
}
function registry() {
  return new $ZodRegistry();
}
(_a = globalThis).__zod_globalRegistry ?? (_a.__zod_globalRegistry = registry());
const globalRegistry = globalThis.__zod_globalRegistry;
// @__NO_SIDE_EFFECTS__
function _string(Class, params) {
  return new Class({
    type: "string",
    ...normalizeParams(params)
  });
}
// @__NO_SIDE_EFFECTS__
function _email(Class, params) {
  return new Class({
    type: "string",
    format: "email",
    check: "string_format",
    abort: false,
    ...normalizeParams(params)
  });
}
// @__NO_SIDE_EFFECTS__
function _guid(Class, params) {
  return new Class({
    type: "string",
    format: "guid",
    check: "string_format",
    abort: false,
    ...normalizeParams(params)
  });
}
// @__NO_SIDE_EFFECTS__
function _uuid(Class, params) {
  return new Class({
    type: "string",
    format: "uuid",
    check: "string_format",
    abort: false,
    ...normalizeParams(params)
  });
}
// @__NO_SIDE_EFFECTS__
function _uuidv4(Class, params) {
  return new Class({
    type: "string",
    format: "uuid",
    check: "string_format",
    abort: false,
    version: "v4",
    ...normalizeParams(params)
  });
}
// @__NO_SIDE_EFFECTS__
function _uuidv6(Class, params) {
  return new Class({
    type: "string",
    format: "uuid",
    check: "string_format",
    abort: false,
    version: "v6",
    ...normalizeParams(params)
  });
}
// @__NO_SIDE_EFFECTS__
function _uuidv7(Class, params) {
  return new Class({
    type: "string",
    format: "uuid",
    check: "string_format",
    abort: false,
    version: "v7",
    ...normalizeParams(params)
  });
}
// @__NO_SIDE_EFFECTS__
function _url(Class, params) {
  return new Class({
    type: "string",
    format: "url",
    check: "string_format",
    abort: false,
    ...normalizeParams(params)
  });
}
// @__NO_SIDE_EFFECTS__
function _emoji(Class, params) {
  return new Class({
    type: "string",
    format: "emoji",
    check: "string_format",
    abort: false,
    ...normalizeParams(params)
  });
}
// @__NO_SIDE_EFFECTS__
function _nanoid(Class, params) {
  return new Class({
    type: "string",
    format: "nanoid",
    check: "string_format",
    abort: false,
    ...normalizeParams(params)
  });
}
// @__NO_SIDE_EFFECTS__
function _cuid(Class, params) {
  return new Class({
    type: "string",
    format: "cuid",
    check: "string_format",
    abort: false,
    ...normalizeParams(params)
  });
}
// @__NO_SIDE_EFFECTS__
function _cuid2(Class, params) {
  return new Class({
    type: "string",
    format: "cuid2",
    check: "string_format",
    abort: false,
    ...normalizeParams(params)
  });
}
// @__NO_SIDE_EFFECTS__
function _ulid(Class, params) {
  return new Class({
    type: "string",
    format: "ulid",
    check: "string_format",
    abort: false,
    ...normalizeParams(params)
  });
}
// @__NO_SIDE_EFFECTS__
function _xid(Class, params) {
  return new Class({
    type: "string",
    format: "xid",
    check: "string_format",
    abort: false,
    ...normalizeParams(params)
  });
}
// @__NO_SIDE_EFFECTS__
function _ksuid(Class, params) {
  return new Class({
    type: "string",
    format: "ksuid",
    check: "string_format",
    abort: false,
    ...normalizeParams(params)
  });
}
// @__NO_SIDE_EFFECTS__
function _ipv4(Class, params) {
  return new Class({
    type: "string",
    format: "ipv4",
    check: "string_format",
    abort: false,
    ...normalizeParams(params)
  });
}
// @__NO_SIDE_EFFECTS__
function _ipv6(Class, params) {
  return new Class({
    type: "string",
    format: "ipv6",
    check: "string_format",
    abort: false,
    ...normalizeParams(params)
  });
}
// @__NO_SIDE_EFFECTS__
function _cidrv4(Class, params) {
  return new Class({
    type: "string",
    format: "cidrv4",
    check: "string_format",
    abort: false,
    ...normalizeParams(params)
  });
}
// @__NO_SIDE_EFFECTS__
function _cidrv6(Class, params) {
  return new Class({
    type: "string",
    format: "cidrv6",
    check: "string_format",
    abort: false,
    ...normalizeParams(params)
  });
}
// @__NO_SIDE_EFFECTS__
function _base64(Class, params) {
  return new Class({
    type: "string",
    format: "base64",
    check: "string_format",
    abort: false,
    ...normalizeParams(params)
  });
}
// @__NO_SIDE_EFFECTS__
function _base64url(Class, params) {
  return new Class({
    type: "string",
    format: "base64url",
    check: "string_format",
    abort: false,
    ...normalizeParams(params)
  });
}
// @__NO_SIDE_EFFECTS__
function _e164(Class, params) {
  return new Class({
    type: "string",
    format: "e164",
    check: "string_format",
    abort: false,
    ...normalizeParams(params)
  });
}
// @__NO_SIDE_EFFECTS__
function _jwt(Class, params) {
  return new Class({
    type: "string",
    format: "jwt",
    check: "string_format",
    abort: false,
    ...normalizeParams(params)
  });
}
// @__NO_SIDE_EFFECTS__
function _isoDateTime(Class, params) {
  return new Class({
    type: "string",
    format: "datetime",
    check: "string_format",
    offset: false,
    local: false,
    precision: null,
    ...normalizeParams(params)
  });
}
// @__NO_SIDE_EFFECTS__
function _isoDate(Class, params) {
  return new Class({
    type: "string",
    format: "date",
    check: "string_format",
    ...normalizeParams(params)
  });
}
// @__NO_SIDE_EFFECTS__
function _isoTime(Class, params) {
  return new Class({
    type: "string",
    format: "time",
    check: "string_format",
    precision: null,
    ...normalizeParams(params)
  });
}
// @__NO_SIDE_EFFECTS__
function _isoDuration(Class, params) {
  return new Class({
    type: "string",
    format: "duration",
    check: "string_format",
    ...normalizeParams(params)
  });
}
// @__NO_SIDE_EFFECTS__
function _number(Class, params) {
  return new Class({
    type: "number",
    checks: [],
    ...normalizeParams(params)
  });
}
// @__NO_SIDE_EFFECTS__
function _int(Class, params) {
  return new Class({
    type: "number",
    check: "number_format",
    abort: false,
    format: "safeint",
    ...normalizeParams(params)
  });
}
// @__NO_SIDE_EFFECTS__
function _boolean(Class, params) {
  return new Class({
    type: "boolean",
    ...normalizeParams(params)
  });
}
// @__NO_SIDE_EFFECTS__
function _unknown(Class) {
  return new Class({
    type: "unknown"
  });
}
// @__NO_SIDE_EFFECTS__
function _never(Class, params) {
  return new Class({
    type: "never",
    ...normalizeParams(params)
  });
}
// @__NO_SIDE_EFFECTS__
function _lt(value, params) {
  return new $ZodCheckLessThan({
    check: "less_than",
    ...normalizeParams(params),
    value,
    inclusive: false
  });
}
// @__NO_SIDE_EFFECTS__
function _lte(value, params) {
  return new $ZodCheckLessThan({
    check: "less_than",
    ...normalizeParams(params),
    value,
    inclusive: true
  });
}
// @__NO_SIDE_EFFECTS__
function _gt(value, params) {
  return new $ZodCheckGreaterThan({
    check: "greater_than",
    ...normalizeParams(params),
    value,
    inclusive: false
  });
}
// @__NO_SIDE_EFFECTS__
function _gte(value, params) {
  return new $ZodCheckGreaterThan({
    check: "greater_than",
    ...normalizeParams(params),
    value,
    inclusive: true
  });
}
// @__NO_SIDE_EFFECTS__
function _multipleOf(value, params) {
  return new $ZodCheckMultipleOf({
    check: "multiple_of",
    ...normalizeParams(params),
    value
  });
}
// @__NO_SIDE_EFFECTS__
function _maxLength(maximum, params) {
  const ch = new $ZodCheckMaxLength({
    check: "max_length",
    ...normalizeParams(params),
    maximum
  });
  return ch;
}
// @__NO_SIDE_EFFECTS__
function _minLength(minimum, params) {
  return new $ZodCheckMinLength({
    check: "min_length",
    ...normalizeParams(params),
    minimum
  });
}
// @__NO_SIDE_EFFECTS__
function _length(length, params) {
  return new $ZodCheckLengthEquals({
    check: "length_equals",
    ...normalizeParams(params),
    length
  });
}
// @__NO_SIDE_EFFECTS__
function _regex(pattern, params) {
  return new $ZodCheckRegex({
    check: "string_format",
    format: "regex",
    ...normalizeParams(params),
    pattern
  });
}
// @__NO_SIDE_EFFECTS__
function _lowercase(params) {
  return new $ZodCheckLowerCase({
    check: "string_format",
    format: "lowercase",
    ...normalizeParams(params)
  });
}
// @__NO_SIDE_EFFECTS__
function _uppercase(params) {
  return new $ZodCheckUpperCase({
    check: "string_format",
    format: "uppercase",
    ...normalizeParams(params)
  });
}
// @__NO_SIDE_EFFECTS__
function _includes(includes, params) {
  return new $ZodCheckIncludes({
    check: "string_format",
    format: "includes",
    ...normalizeParams(params),
    includes
  });
}
// @__NO_SIDE_EFFECTS__
function _startsWith(prefix, params) {
  return new $ZodCheckStartsWith({
    check: "string_format",
    format: "starts_with",
    ...normalizeParams(params),
    prefix
  });
}
// @__NO_SIDE_EFFECTS__
function _endsWith(suffix, params) {
  return new $ZodCheckEndsWith({
    check: "string_format",
    format: "ends_with",
    ...normalizeParams(params),
    suffix
  });
}
// @__NO_SIDE_EFFECTS__
function _overwrite(tx) {
  return new $ZodCheckOverwrite({
    check: "overwrite",
    tx
  });
}
// @__NO_SIDE_EFFECTS__
function _normalize(form) {
  return /* @__PURE__ */ _overwrite((input) => input.normalize(form));
}
// @__NO_SIDE_EFFECTS__
function _trim() {
  return /* @__PURE__ */ _overwrite((input) => input.trim());
}
// @__NO_SIDE_EFFECTS__
function _toLowerCase() {
  return /* @__PURE__ */ _overwrite((input) => input.toLowerCase());
}
// @__NO_SIDE_EFFECTS__
function _toUpperCase() {
  return /* @__PURE__ */ _overwrite((input) => input.toUpperCase());
}
// @__NO_SIDE_EFFECTS__
function _slugify() {
  return /* @__PURE__ */ _overwrite((input) => slugify(input));
}
// @__NO_SIDE_EFFECTS__
function _array(Class, element, params) {
  return new Class({
    type: "array",
    element,
    // get element() {
    //   return element;
    // },
    ...normalizeParams(params)
  });
}
// @__NO_SIDE_EFFECTS__
function _refine(Class, fn, _params) {
  const schema = new Class({
    type: "custom",
    check: "custom",
    fn,
    ...normalizeParams(_params)
  });
  return schema;
}
// @__NO_SIDE_EFFECTS__
function _superRefine(fn) {
  const ch = /* @__PURE__ */ _check((payload) => {
    payload.addIssue = (issue$1) => {
      if (typeof issue$1 === "string") {
        payload.issues.push(issue(issue$1, payload.value, ch._zod.def));
      } else {
        const _issue = issue$1;
        if (_issue.fatal)
          _issue.continue = false;
        _issue.code ?? (_issue.code = "custom");
        _issue.input ?? (_issue.input = payload.value);
        _issue.inst ?? (_issue.inst = ch);
        _issue.continue ?? (_issue.continue = !ch._zod.def.abort);
        payload.issues.push(issue(_issue));
      }
    };
    return fn(payload.value, payload);
  });
  return ch;
}
// @__NO_SIDE_EFFECTS__
function _check(fn, params) {
  const ch = new $ZodCheck({
    check: "custom",
    ...normalizeParams(params)
  });
  ch._zod.check = fn;
  return ch;
}
function initializeContext(params) {
  let target = (params == null ? void 0 : params.target) ?? "draft-2020-12";
  if (target === "draft-4")
    target = "draft-04";
  if (target === "draft-7")
    target = "draft-07";
  return {
    processors: params.processors ?? {},
    metadataRegistry: (params == null ? void 0 : params.metadata) ?? globalRegistry,
    target,
    unrepresentable: (params == null ? void 0 : params.unrepresentable) ?? "throw",
    override: (params == null ? void 0 : params.override) ?? (() => {
    }),
    io: (params == null ? void 0 : params.io) ?? "output",
    counter: 0,
    seen: /* @__PURE__ */ new Map(),
    cycles: (params == null ? void 0 : params.cycles) ?? "ref",
    reused: (params == null ? void 0 : params.reused) ?? "inline",
    external: (params == null ? void 0 : params.external) ?? void 0
  };
}
function process$1(schema, ctx, _params = { path: [], schemaPath: [] }) {
  var _a4, _b;
  var _a3;
  const def = schema._zod.def;
  const seen = ctx.seen.get(schema);
  if (seen) {
    seen.count++;
    const isCycle = _params.schemaPath.includes(schema);
    if (isCycle) {
      seen.cycle = _params.path;
    }
    return seen.schema;
  }
  const result = { schema: {}, count: 1, cycle: void 0, path: _params.path };
  ctx.seen.set(schema, result);
  const overrideSchema = (_b = (_a4 = schema._zod).toJSONSchema) == null ? void 0 : _b.call(_a4);
  if (overrideSchema) {
    result.schema = overrideSchema;
  } else {
    const params = {
      ..._params,
      schemaPath: [..._params.schemaPath, schema],
      path: _params.path
    };
    if (schema._zod.processJSONSchema) {
      schema._zod.processJSONSchema(ctx, result.schema, params);
    } else {
      const _json = result.schema;
      const processor = ctx.processors[def.type];
      if (!processor) {
        throw new Error(`[toJSONSchema]: Non-representable type encountered: ${def.type}`);
      }
      processor(schema, ctx, _json, params);
    }
    const parent = schema._zod.parent;
    if (parent) {
      if (!result.ref)
        result.ref = parent;
      process$1(parent, ctx, params);
      ctx.seen.get(parent).isParent = true;
    }
  }
  const meta = ctx.metadataRegistry.get(schema);
  if (meta)
    Object.assign(result.schema, meta);
  if (ctx.io === "input" && isTransforming(schema)) {
    delete result.schema.examples;
    delete result.schema.default;
  }
  if (ctx.io === "input" && result.schema._prefault)
    (_a3 = result.schema).default ?? (_a3.default = result.schema._prefault);
  delete result.schema._prefault;
  const _result = ctx.seen.get(schema);
  return _result.schema;
}
function extractDefs(ctx, schema) {
  var _a3, _b, _c, _d;
  const root = ctx.seen.get(schema);
  if (!root)
    throw new Error("Unprocessed schema. This is a bug in Zod.");
  const idToSchema = /* @__PURE__ */ new Map();
  for (const entry of ctx.seen.entries()) {
    const id = (_a3 = ctx.metadataRegistry.get(entry[0])) == null ? void 0 : _a3.id;
    if (id) {
      const existing = idToSchema.get(id);
      if (existing && existing !== entry[0]) {
        throw new Error(`Duplicate schema id "${id}" detected during JSON Schema conversion. Two different schemas cannot share the same id when converted together.`);
      }
      idToSchema.set(id, entry[0]);
    }
  }
  const makeURI = (entry) => {
    var _a4;
    const defsSegment = ctx.target === "draft-2020-12" ? "$defs" : "definitions";
    if (ctx.external) {
      const externalId = (_a4 = ctx.external.registry.get(entry[0])) == null ? void 0 : _a4.id;
      const uriGenerator = ctx.external.uri ?? ((id2) => id2);
      if (externalId) {
        return { ref: uriGenerator(externalId) };
      }
      const id = entry[1].defId ?? entry[1].schema.id ?? `schema${ctx.counter++}`;
      entry[1].defId = id;
      return { defId: id, ref: `${uriGenerator("__shared")}#/${defsSegment}/${id}` };
    }
    if (entry[1] === root) {
      return { ref: "#" };
    }
    const uriPrefix = `#`;
    const defUriPrefix = `${uriPrefix}/${defsSegment}/`;
    const defId = entry[1].schema.id ?? `__schema${ctx.counter++}`;
    return { defId, ref: defUriPrefix + defId };
  };
  const extractToDef = (entry) => {
    if (entry[1].schema.$ref) {
      return;
    }
    const seen = entry[1];
    const { ref, defId } = makeURI(entry);
    seen.def = { ...seen.schema };
    if (defId)
      seen.defId = defId;
    const schema2 = seen.schema;
    for (const key in schema2) {
      delete schema2[key];
    }
    schema2.$ref = ref;
  };
  if (ctx.cycles === "throw") {
    for (const entry of ctx.seen.entries()) {
      const seen = entry[1];
      if (seen.cycle) {
        throw new Error(`Cycle detected: #/${(_b = seen.cycle) == null ? void 0 : _b.join("/")}/<root>

Set the \`cycles\` parameter to \`"ref"\` to resolve cyclical schemas with defs.`);
      }
    }
  }
  for (const entry of ctx.seen.entries()) {
    const seen = entry[1];
    if (schema === entry[0]) {
      extractToDef(entry);
      continue;
    }
    if (ctx.external) {
      const ext = (_c = ctx.external.registry.get(entry[0])) == null ? void 0 : _c.id;
      if (schema !== entry[0] && ext) {
        extractToDef(entry);
        continue;
      }
    }
    const id = (_d = ctx.metadataRegistry.get(entry[0])) == null ? void 0 : _d.id;
    if (id) {
      extractToDef(entry);
      continue;
    }
    if (seen.cycle) {
      extractToDef(entry);
      continue;
    }
    if (seen.count > 1) {
      if (ctx.reused === "ref") {
        extractToDef(entry);
        continue;
      }
    }
  }
}
function finalize(ctx, schema) {
  var _a3, _b, _c;
  const root = ctx.seen.get(schema);
  if (!root)
    throw new Error("Unprocessed schema. This is a bug in Zod.");
  const flattenRef = (zodSchema) => {
    const seen = ctx.seen.get(zodSchema);
    if (seen.ref === null)
      return;
    const schema2 = seen.def ?? seen.schema;
    const _cached = { ...schema2 };
    const ref = seen.ref;
    seen.ref = null;
    if (ref) {
      flattenRef(ref);
      const refSeen = ctx.seen.get(ref);
      const refSchema = refSeen.schema;
      if (refSchema.$ref && (ctx.target === "draft-07" || ctx.target === "draft-04" || ctx.target === "openapi-3.0")) {
        schema2.allOf = schema2.allOf ?? [];
        schema2.allOf.push(refSchema);
      } else {
        Object.assign(schema2, refSchema);
      }
      Object.assign(schema2, _cached);
      const isParentRef = zodSchema._zod.parent === ref;
      if (isParentRef) {
        for (const key in schema2) {
          if (key === "$ref" || key === "allOf")
            continue;
          if (!(key in _cached)) {
            delete schema2[key];
          }
        }
      }
      if (refSchema.$ref && refSeen.def) {
        for (const key in schema2) {
          if (key === "$ref" || key === "allOf")
            continue;
          if (key in refSeen.def && JSON.stringify(schema2[key]) === JSON.stringify(refSeen.def[key])) {
            delete schema2[key];
          }
        }
      }
    }
    const parent = zodSchema._zod.parent;
    if (parent && parent !== ref) {
      flattenRef(parent);
      const parentSeen = ctx.seen.get(parent);
      if (parentSeen == null ? void 0 : parentSeen.schema.$ref) {
        schema2.$ref = parentSeen.schema.$ref;
        if (parentSeen.def) {
          for (const key in schema2) {
            if (key === "$ref" || key === "allOf")
              continue;
            if (key in parentSeen.def && JSON.stringify(schema2[key]) === JSON.stringify(parentSeen.def[key])) {
              delete schema2[key];
            }
          }
        }
      }
    }
    ctx.override({
      zodSchema,
      jsonSchema: schema2,
      path: seen.path ?? []
    });
  };
  for (const entry of [...ctx.seen.entries()].reverse()) {
    flattenRef(entry[0]);
  }
  const result = {};
  if (ctx.target === "draft-2020-12") {
    result.$schema = "https://json-schema.org/draft/2020-12/schema";
  } else if (ctx.target === "draft-07") {
    result.$schema = "http://json-schema.org/draft-07/schema#";
  } else if (ctx.target === "draft-04") {
    result.$schema = "http://json-schema.org/draft-04/schema#";
  } else if (ctx.target === "openapi-3.0") ;
  else ;
  if ((_a3 = ctx.external) == null ? void 0 : _a3.uri) {
    const id = (_b = ctx.external.registry.get(schema)) == null ? void 0 : _b.id;
    if (!id)
      throw new Error("Schema is missing an `id` property");
    result.$id = ctx.external.uri(id);
  }
  Object.assign(result, root.def ?? root.schema);
  const defs = ((_c = ctx.external) == null ? void 0 : _c.defs) ?? {};
  for (const entry of ctx.seen.entries()) {
    const seen = entry[1];
    if (seen.def && seen.defId) {
      defs[seen.defId] = seen.def;
    }
  }
  if (ctx.external) ;
  else {
    if (Object.keys(defs).length > 0) {
      if (ctx.target === "draft-2020-12") {
        result.$defs = defs;
      } else {
        result.definitions = defs;
      }
    }
  }
  try {
    const finalized = JSON.parse(JSON.stringify(result));
    Object.defineProperty(finalized, "~standard", {
      value: {
        ...schema["~standard"],
        jsonSchema: {
          input: createStandardJSONSchemaMethod(schema, "input", ctx.processors),
          output: createStandardJSONSchemaMethod(schema, "output", ctx.processors)
        }
      },
      enumerable: false,
      writable: false
    });
    return finalized;
  } catch (_err) {
    throw new Error("Error converting schema to JSON.");
  }
}
function isTransforming(_schema, _ctx) {
  const ctx = _ctx ?? { seen: /* @__PURE__ */ new Set() };
  if (ctx.seen.has(_schema))
    return false;
  ctx.seen.add(_schema);
  const def = _schema._zod.def;
  if (def.type === "transform")
    return true;
  if (def.type === "array")
    return isTransforming(def.element, ctx);
  if (def.type === "set")
    return isTransforming(def.valueType, ctx);
  if (def.type === "lazy")
    return isTransforming(def.getter(), ctx);
  if (def.type === "promise" || def.type === "optional" || def.type === "nonoptional" || def.type === "nullable" || def.type === "readonly" || def.type === "default" || def.type === "prefault") {
    return isTransforming(def.innerType, ctx);
  }
  if (def.type === "intersection") {
    return isTransforming(def.left, ctx) || isTransforming(def.right, ctx);
  }
  if (def.type === "record" || def.type === "map") {
    return isTransforming(def.keyType, ctx) || isTransforming(def.valueType, ctx);
  }
  if (def.type === "pipe") {
    return isTransforming(def.in, ctx) || isTransforming(def.out, ctx);
  }
  if (def.type === "object") {
    for (const key in def.shape) {
      if (isTransforming(def.shape[key], ctx))
        return true;
    }
    return false;
  }
  if (def.type === "union") {
    for (const option of def.options) {
      if (isTransforming(option, ctx))
        return true;
    }
    return false;
  }
  if (def.type === "tuple") {
    for (const item of def.items) {
      if (isTransforming(item, ctx))
        return true;
    }
    if (def.rest && isTransforming(def.rest, ctx))
      return true;
    return false;
  }
  return false;
}
const createToJSONSchemaMethod = (schema, processors = {}) => (params) => {
  const ctx = initializeContext({ ...params, processors });
  process$1(schema, ctx);
  extractDefs(ctx, schema);
  return finalize(ctx, schema);
};
const createStandardJSONSchemaMethod = (schema, io, processors = {}) => (params) => {
  const { libraryOptions, target } = params ?? {};
  const ctx = initializeContext({ ...libraryOptions ?? {}, target, io, processors });
  process$1(schema, ctx);
  extractDefs(ctx, schema);
  return finalize(ctx, schema);
};
const formatMap = {
  guid: "uuid",
  url: "uri",
  datetime: "date-time",
  json_string: "json-string",
  regex: ""
  // do not set
};
const stringProcessor = (schema, ctx, _json, _params) => {
  const json = _json;
  json.type = "string";
  const { minimum, maximum, format, patterns, contentEncoding } = schema._zod.bag;
  if (typeof minimum === "number")
    json.minLength = minimum;
  if (typeof maximum === "number")
    json.maxLength = maximum;
  if (format) {
    json.format = formatMap[format] ?? format;
    if (json.format === "")
      delete json.format;
    if (format === "time") {
      delete json.format;
    }
  }
  if (contentEncoding)
    json.contentEncoding = contentEncoding;
  if (patterns && patterns.size > 0) {
    const regexes = [...patterns];
    if (regexes.length === 1)
      json.pattern = regexes[0].source;
    else if (regexes.length > 1) {
      json.allOf = [
        ...regexes.map((regex) => ({
          ...ctx.target === "draft-07" || ctx.target === "draft-04" || ctx.target === "openapi-3.0" ? { type: "string" } : {},
          pattern: regex.source
        }))
      ];
    }
  }
};
const numberProcessor = (schema, ctx, _json, _params) => {
  const json = _json;
  const { minimum, maximum, format, multipleOf, exclusiveMaximum, exclusiveMinimum } = schema._zod.bag;
  if (typeof format === "string" && format.includes("int"))
    json.type = "integer";
  else
    json.type = "number";
  if (typeof exclusiveMinimum === "number") {
    if (ctx.target === "draft-04" || ctx.target === "openapi-3.0") {
      json.minimum = exclusiveMinimum;
      json.exclusiveMinimum = true;
    } else {
      json.exclusiveMinimum = exclusiveMinimum;
    }
  }
  if (typeof minimum === "number") {
    json.minimum = minimum;
    if (typeof exclusiveMinimum === "number" && ctx.target !== "draft-04") {
      if (exclusiveMinimum >= minimum)
        delete json.minimum;
      else
        delete json.exclusiveMinimum;
    }
  }
  if (typeof exclusiveMaximum === "number") {
    if (ctx.target === "draft-04" || ctx.target === "openapi-3.0") {
      json.maximum = exclusiveMaximum;
      json.exclusiveMaximum = true;
    } else {
      json.exclusiveMaximum = exclusiveMaximum;
    }
  }
  if (typeof maximum === "number") {
    json.maximum = maximum;
    if (typeof exclusiveMaximum === "number" && ctx.target !== "draft-04") {
      if (exclusiveMaximum <= maximum)
        delete json.maximum;
      else
        delete json.exclusiveMaximum;
    }
  }
  if (typeof multipleOf === "number")
    json.multipleOf = multipleOf;
};
const booleanProcessor = (_schema, _ctx, json, _params) => {
  json.type = "boolean";
};
const neverProcessor = (_schema, _ctx, json, _params) => {
  json.not = {};
};
const unknownProcessor = (_schema, _ctx, _json, _params) => {
};
const enumProcessor = (schema, _ctx, json, _params) => {
  const def = schema._zod.def;
  const values = getEnumValues(def.entries);
  if (values.every((v) => typeof v === "number"))
    json.type = "number";
  if (values.every((v) => typeof v === "string"))
    json.type = "string";
  json.enum = values;
};
const literalProcessor = (schema, ctx, json, _params) => {
  const def = schema._zod.def;
  const vals = [];
  for (const val of def.values) {
    if (val === void 0) {
      if (ctx.unrepresentable === "throw") {
        throw new Error("Literal `undefined` cannot be represented in JSON Schema");
      }
    } else if (typeof val === "bigint") {
      if (ctx.unrepresentable === "throw") {
        throw new Error("BigInt literals cannot be represented in JSON Schema");
      } else {
        vals.push(Number(val));
      }
    } else {
      vals.push(val);
    }
  }
  if (vals.length === 0) ;
  else if (vals.length === 1) {
    const val = vals[0];
    json.type = val === null ? "null" : typeof val;
    if (ctx.target === "draft-04" || ctx.target === "openapi-3.0") {
      json.enum = [val];
    } else {
      json.const = val;
    }
  } else {
    if (vals.every((v) => typeof v === "number"))
      json.type = "number";
    if (vals.every((v) => typeof v === "string"))
      json.type = "string";
    if (vals.every((v) => typeof v === "boolean"))
      json.type = "boolean";
    if (vals.every((v) => v === null))
      json.type = "null";
    json.enum = vals;
  }
};
const customProcessor = (_schema, ctx, _json, _params) => {
  if (ctx.unrepresentable === "throw") {
    throw new Error("Custom types cannot be represented in JSON Schema");
  }
};
const transformProcessor = (_schema, ctx, _json, _params) => {
  if (ctx.unrepresentable === "throw") {
    throw new Error("Transforms cannot be represented in JSON Schema");
  }
};
const arrayProcessor = (schema, ctx, _json, params) => {
  const json = _json;
  const def = schema._zod.def;
  const { minimum, maximum } = schema._zod.bag;
  if (typeof minimum === "number")
    json.minItems = minimum;
  if (typeof maximum === "number")
    json.maxItems = maximum;
  json.type = "array";
  json.items = process$1(def.element, ctx, { ...params, path: [...params.path, "items"] });
};
const objectProcessor = (schema, ctx, _json, params) => {
  var _a3;
  const json = _json;
  const def = schema._zod.def;
  json.type = "object";
  json.properties = {};
  const shape = def.shape;
  for (const key in shape) {
    json.properties[key] = process$1(shape[key], ctx, {
      ...params,
      path: [...params.path, "properties", key]
    });
  }
  const allKeys = new Set(Object.keys(shape));
  const requiredKeys = new Set([...allKeys].filter((key) => {
    const v = def.shape[key]._zod;
    if (ctx.io === "input") {
      return v.optin === void 0;
    } else {
      return v.optout === void 0;
    }
  }));
  if (requiredKeys.size > 0) {
    json.required = Array.from(requiredKeys);
  }
  if (((_a3 = def.catchall) == null ? void 0 : _a3._zod.def.type) === "never") {
    json.additionalProperties = false;
  } else if (!def.catchall) {
    if (ctx.io === "output")
      json.additionalProperties = false;
  } else if (def.catchall) {
    json.additionalProperties = process$1(def.catchall, ctx, {
      ...params,
      path: [...params.path, "additionalProperties"]
    });
  }
};
const unionProcessor = (schema, ctx, json, params) => {
  const def = schema._zod.def;
  const isExclusive = def.inclusive === false;
  const options = def.options.map((x, i) => process$1(x, ctx, {
    ...params,
    path: [...params.path, isExclusive ? "oneOf" : "anyOf", i]
  }));
  if (isExclusive) {
    json.oneOf = options;
  } else {
    json.anyOf = options;
  }
};
const intersectionProcessor = (schema, ctx, json, params) => {
  const def = schema._zod.def;
  const a = process$1(def.left, ctx, {
    ...params,
    path: [...params.path, "allOf", 0]
  });
  const b = process$1(def.right, ctx, {
    ...params,
    path: [...params.path, "allOf", 1]
  });
  const isSimpleIntersection = (val) => "allOf" in val && Object.keys(val).length === 1;
  const allOf = [
    ...isSimpleIntersection(a) ? a.allOf : [a],
    ...isSimpleIntersection(b) ? b.allOf : [b]
  ];
  json.allOf = allOf;
};
const tupleProcessor = (schema, ctx, _json, params) => {
  const json = _json;
  const def = schema._zod.def;
  json.type = "array";
  const prefixPath = ctx.target === "draft-2020-12" ? "prefixItems" : "items";
  const restPath = ctx.target === "draft-2020-12" ? "items" : ctx.target === "openapi-3.0" ? "items" : "additionalItems";
  const prefixItems = def.items.map((x, i) => process$1(x, ctx, {
    ...params,
    path: [...params.path, prefixPath, i]
  }));
  const rest = def.rest ? process$1(def.rest, ctx, {
    ...params,
    path: [...params.path, restPath, ...ctx.target === "openapi-3.0" ? [def.items.length] : []]
  }) : null;
  if (ctx.target === "draft-2020-12") {
    json.prefixItems = prefixItems;
    if (rest) {
      json.items = rest;
    }
  } else if (ctx.target === "openapi-3.0") {
    json.items = {
      anyOf: prefixItems
    };
    if (rest) {
      json.items.anyOf.push(rest);
    }
    json.minItems = prefixItems.length;
    if (!rest) {
      json.maxItems = prefixItems.length;
    }
  } else {
    json.items = prefixItems;
    if (rest) {
      json.additionalItems = rest;
    }
  }
  const { minimum, maximum } = schema._zod.bag;
  if (typeof minimum === "number")
    json.minItems = minimum;
  if (typeof maximum === "number")
    json.maxItems = maximum;
};
const recordProcessor = (schema, ctx, _json, params) => {
  const json = _json;
  const def = schema._zod.def;
  json.type = "object";
  const keyType = def.keyType;
  const keyBag = keyType._zod.bag;
  const patterns = keyBag == null ? void 0 : keyBag.patterns;
  if (def.mode === "loose" && patterns && patterns.size > 0) {
    const valueSchema = process$1(def.valueType, ctx, {
      ...params,
      path: [...params.path, "patternProperties", "*"]
    });
    json.patternProperties = {};
    for (const pattern of patterns) {
      json.patternProperties[pattern.source] = valueSchema;
    }
  } else {
    if (ctx.target === "draft-07" || ctx.target === "draft-2020-12") {
      json.propertyNames = process$1(def.keyType, ctx, {
        ...params,
        path: [...params.path, "propertyNames"]
      });
    }
    json.additionalProperties = process$1(def.valueType, ctx, {
      ...params,
      path: [...params.path, "additionalProperties"]
    });
  }
  const keyValues = keyType._zod.values;
  if (keyValues) {
    const validKeyValues = [...keyValues].filter((v) => typeof v === "string" || typeof v === "number");
    if (validKeyValues.length > 0) {
      json.required = validKeyValues;
    }
  }
};
const nullableProcessor = (schema, ctx, json, params) => {
  const def = schema._zod.def;
  const inner = process$1(def.innerType, ctx, params);
  const seen = ctx.seen.get(schema);
  if (ctx.target === "openapi-3.0") {
    seen.ref = def.innerType;
    json.nullable = true;
  } else {
    json.anyOf = [inner, { type: "null" }];
  }
};
const nonoptionalProcessor = (schema, ctx, _json, params) => {
  const def = schema._zod.def;
  process$1(def.innerType, ctx, params);
  const seen = ctx.seen.get(schema);
  seen.ref = def.innerType;
};
const defaultProcessor = (schema, ctx, json, params) => {
  const def = schema._zod.def;
  process$1(def.innerType, ctx, params);
  const seen = ctx.seen.get(schema);
  seen.ref = def.innerType;
  json.default = JSON.parse(JSON.stringify(def.defaultValue));
};
const prefaultProcessor = (schema, ctx, json, params) => {
  const def = schema._zod.def;
  process$1(def.innerType, ctx, params);
  const seen = ctx.seen.get(schema);
  seen.ref = def.innerType;
  if (ctx.io === "input")
    json._prefault = JSON.parse(JSON.stringify(def.defaultValue));
};
const catchProcessor = (schema, ctx, json, params) => {
  const def = schema._zod.def;
  process$1(def.innerType, ctx, params);
  const seen = ctx.seen.get(schema);
  seen.ref = def.innerType;
  let catchValue;
  try {
    catchValue = def.catchValue(void 0);
  } catch {
    throw new Error("Dynamic catch values are not supported in JSON Schema");
  }
  json.default = catchValue;
};
const pipeProcessor = (schema, ctx, _json, params) => {
  const def = schema._zod.def;
  const innerType = ctx.io === "input" ? def.in._zod.def.type === "transform" ? def.out : def.in : def.out;
  process$1(innerType, ctx, params);
  const seen = ctx.seen.get(schema);
  seen.ref = innerType;
};
const readonlyProcessor = (schema, ctx, json, params) => {
  const def = schema._zod.def;
  process$1(def.innerType, ctx, params);
  const seen = ctx.seen.get(schema);
  seen.ref = def.innerType;
  json.readOnly = true;
};
const optionalProcessor = (schema, ctx, _json, params) => {
  const def = schema._zod.def;
  process$1(def.innerType, ctx, params);
  const seen = ctx.seen.get(schema);
  seen.ref = def.innerType;
};
const lazyProcessor = (schema, ctx, _json, params) => {
  const innerType = schema._zod.innerType;
  process$1(innerType, ctx, params);
  const seen = ctx.seen.get(schema);
  seen.ref = innerType;
};
const ZodISODateTime = /* @__PURE__ */ $constructor("ZodISODateTime", (inst, def) => {
  $ZodISODateTime.init(inst, def);
  ZodStringFormat.init(inst, def);
});
function datetime(params) {
  return /* @__PURE__ */ _isoDateTime(ZodISODateTime, params);
}
const ZodISODate = /* @__PURE__ */ $constructor("ZodISODate", (inst, def) => {
  $ZodISODate.init(inst, def);
  ZodStringFormat.init(inst, def);
});
function date(params) {
  return /* @__PURE__ */ _isoDate(ZodISODate, params);
}
const ZodISOTime = /* @__PURE__ */ $constructor("ZodISOTime", (inst, def) => {
  $ZodISOTime.init(inst, def);
  ZodStringFormat.init(inst, def);
});
function time(params) {
  return /* @__PURE__ */ _isoTime(ZodISOTime, params);
}
const ZodISODuration = /* @__PURE__ */ $constructor("ZodISODuration", (inst, def) => {
  $ZodISODuration.init(inst, def);
  ZodStringFormat.init(inst, def);
});
function duration(params) {
  return /* @__PURE__ */ _isoDuration(ZodISODuration, params);
}
const initializer = (inst, issues) => {
  $ZodError.init(inst, issues);
  inst.name = "ZodError";
  Object.defineProperties(inst, {
    format: {
      value: (mapper) => formatError(inst, mapper)
      // enumerable: false,
    },
    flatten: {
      value: (mapper) => flattenError(inst, mapper)
      // enumerable: false,
    },
    addIssue: {
      value: (issue2) => {
        inst.issues.push(issue2);
        inst.message = JSON.stringify(inst.issues, jsonStringifyReplacer, 2);
      }
      // enumerable: false,
    },
    addIssues: {
      value: (issues2) => {
        inst.issues.push(...issues2);
        inst.message = JSON.stringify(inst.issues, jsonStringifyReplacer, 2);
      }
      // enumerable: false,
    },
    isEmpty: {
      get() {
        return inst.issues.length === 0;
      }
      // enumerable: false,
    }
  });
};
const ZodRealError = $constructor("ZodError", initializer, {
  Parent: Error
});
const parse = /* @__PURE__ */ _parse(ZodRealError);
const parseAsync = /* @__PURE__ */ _parseAsync(ZodRealError);
const safeParse = /* @__PURE__ */ _safeParse(ZodRealError);
const safeParseAsync = /* @__PURE__ */ _safeParseAsync(ZodRealError);
const encode = /* @__PURE__ */ _encode(ZodRealError);
const decode = /* @__PURE__ */ _decode(ZodRealError);
const encodeAsync = /* @__PURE__ */ _encodeAsync(ZodRealError);
const decodeAsync = /* @__PURE__ */ _decodeAsync(ZodRealError);
const safeEncode = /* @__PURE__ */ _safeEncode(ZodRealError);
const safeDecode = /* @__PURE__ */ _safeDecode(ZodRealError);
const safeEncodeAsync = /* @__PURE__ */ _safeEncodeAsync(ZodRealError);
const safeDecodeAsync = /* @__PURE__ */ _safeDecodeAsync(ZodRealError);
const ZodType = /* @__PURE__ */ $constructor("ZodType", (inst, def) => {
  $ZodType.init(inst, def);
  Object.assign(inst["~standard"], {
    jsonSchema: {
      input: createStandardJSONSchemaMethod(inst, "input"),
      output: createStandardJSONSchemaMethod(inst, "output")
    }
  });
  inst.toJSONSchema = createToJSONSchemaMethod(inst, {});
  inst.def = def;
  inst.type = def.type;
  Object.defineProperty(inst, "_def", { value: def });
  inst.check = (...checks) => {
    return inst.clone(mergeDefs(def, {
      checks: [
        ...def.checks ?? [],
        ...checks.map((ch) => typeof ch === "function" ? { _zod: { check: ch, def: { check: "custom" }, onattach: [] } } : ch)
      ]
    }), {
      parent: true
    });
  };
  inst.with = inst.check;
  inst.clone = (def2, params) => clone(inst, def2, params);
  inst.brand = () => inst;
  inst.register = ((reg, meta) => {
    reg.add(inst, meta);
    return inst;
  });
  inst.parse = (data, params) => parse(inst, data, params, { callee: inst.parse });
  inst.safeParse = (data, params) => safeParse(inst, data, params);
  inst.parseAsync = async (data, params) => parseAsync(inst, data, params, { callee: inst.parseAsync });
  inst.safeParseAsync = async (data, params) => safeParseAsync(inst, data, params);
  inst.spa = inst.safeParseAsync;
  inst.encode = (data, params) => encode(inst, data, params);
  inst.decode = (data, params) => decode(inst, data, params);
  inst.encodeAsync = async (data, params) => encodeAsync(inst, data, params);
  inst.decodeAsync = async (data, params) => decodeAsync(inst, data, params);
  inst.safeEncode = (data, params) => safeEncode(inst, data, params);
  inst.safeDecode = (data, params) => safeDecode(inst, data, params);
  inst.safeEncodeAsync = async (data, params) => safeEncodeAsync(inst, data, params);
  inst.safeDecodeAsync = async (data, params) => safeDecodeAsync(inst, data, params);
  inst.refine = (check, params) => inst.check(refine(check, params));
  inst.superRefine = (refinement) => inst.check(superRefine(refinement));
  inst.overwrite = (fn) => inst.check(/* @__PURE__ */ _overwrite(fn));
  inst.optional = () => optional(inst);
  inst.exactOptional = () => exactOptional(inst);
  inst.nullable = () => nullable(inst);
  inst.nullish = () => optional(nullable(inst));
  inst.nonoptional = (params) => nonoptional(inst, params);
  inst.array = () => array(inst);
  inst.or = (arg) => union([inst, arg]);
  inst.and = (arg) => intersection(inst, arg);
  inst.transform = (tx) => pipe(inst, transform(tx));
  inst.default = (def2) => _default(inst, def2);
  inst.prefault = (def2) => prefault(inst, def2);
  inst.catch = (params) => _catch(inst, params);
  inst.pipe = (target) => pipe(inst, target);
  inst.readonly = () => readonly(inst);
  inst.describe = (description) => {
    const cl = inst.clone();
    globalRegistry.add(cl, { description });
    return cl;
  };
  Object.defineProperty(inst, "description", {
    get() {
      var _a3;
      return (_a3 = globalRegistry.get(inst)) == null ? void 0 : _a3.description;
    },
    configurable: true
  });
  inst.meta = (...args) => {
    if (args.length === 0) {
      return globalRegistry.get(inst);
    }
    const cl = inst.clone();
    globalRegistry.add(cl, args[0]);
    return cl;
  };
  inst.isOptional = () => inst.safeParse(void 0).success;
  inst.isNullable = () => inst.safeParse(null).success;
  inst.apply = (fn) => fn(inst);
  return inst;
});
const _ZodString = /* @__PURE__ */ $constructor("_ZodString", (inst, def) => {
  $ZodString.init(inst, def);
  ZodType.init(inst, def);
  inst._zod.processJSONSchema = (ctx, json, params) => stringProcessor(inst, ctx, json);
  const bag = inst._zod.bag;
  inst.format = bag.format ?? null;
  inst.minLength = bag.minimum ?? null;
  inst.maxLength = bag.maximum ?? null;
  inst.regex = (...args) => inst.check(/* @__PURE__ */ _regex(...args));
  inst.includes = (...args) => inst.check(/* @__PURE__ */ _includes(...args));
  inst.startsWith = (...args) => inst.check(/* @__PURE__ */ _startsWith(...args));
  inst.endsWith = (...args) => inst.check(/* @__PURE__ */ _endsWith(...args));
  inst.min = (...args) => inst.check(/* @__PURE__ */ _minLength(...args));
  inst.max = (...args) => inst.check(/* @__PURE__ */ _maxLength(...args));
  inst.length = (...args) => inst.check(/* @__PURE__ */ _length(...args));
  inst.nonempty = (...args) => inst.check(/* @__PURE__ */ _minLength(1, ...args));
  inst.lowercase = (params) => inst.check(/* @__PURE__ */ _lowercase(params));
  inst.uppercase = (params) => inst.check(/* @__PURE__ */ _uppercase(params));
  inst.trim = () => inst.check(/* @__PURE__ */ _trim());
  inst.normalize = (...args) => inst.check(/* @__PURE__ */ _normalize(...args));
  inst.toLowerCase = () => inst.check(/* @__PURE__ */ _toLowerCase());
  inst.toUpperCase = () => inst.check(/* @__PURE__ */ _toUpperCase());
  inst.slugify = () => inst.check(/* @__PURE__ */ _slugify());
});
const ZodString = /* @__PURE__ */ $constructor("ZodString", (inst, def) => {
  $ZodString.init(inst, def);
  _ZodString.init(inst, def);
  inst.email = (params) => inst.check(/* @__PURE__ */ _email(ZodEmail, params));
  inst.url = (params) => inst.check(/* @__PURE__ */ _url(ZodURL, params));
  inst.jwt = (params) => inst.check(/* @__PURE__ */ _jwt(ZodJWT, params));
  inst.emoji = (params) => inst.check(/* @__PURE__ */ _emoji(ZodEmoji, params));
  inst.guid = (params) => inst.check(/* @__PURE__ */ _guid(ZodGUID, params));
  inst.uuid = (params) => inst.check(/* @__PURE__ */ _uuid(ZodUUID, params));
  inst.uuidv4 = (params) => inst.check(/* @__PURE__ */ _uuidv4(ZodUUID, params));
  inst.uuidv6 = (params) => inst.check(/* @__PURE__ */ _uuidv6(ZodUUID, params));
  inst.uuidv7 = (params) => inst.check(/* @__PURE__ */ _uuidv7(ZodUUID, params));
  inst.nanoid = (params) => inst.check(/* @__PURE__ */ _nanoid(ZodNanoID, params));
  inst.guid = (params) => inst.check(/* @__PURE__ */ _guid(ZodGUID, params));
  inst.cuid = (params) => inst.check(/* @__PURE__ */ _cuid(ZodCUID, params));
  inst.cuid2 = (params) => inst.check(/* @__PURE__ */ _cuid2(ZodCUID2, params));
  inst.ulid = (params) => inst.check(/* @__PURE__ */ _ulid(ZodULID, params));
  inst.base64 = (params) => inst.check(/* @__PURE__ */ _base64(ZodBase64, params));
  inst.base64url = (params) => inst.check(/* @__PURE__ */ _base64url(ZodBase64URL, params));
  inst.xid = (params) => inst.check(/* @__PURE__ */ _xid(ZodXID, params));
  inst.ksuid = (params) => inst.check(/* @__PURE__ */ _ksuid(ZodKSUID, params));
  inst.ipv4 = (params) => inst.check(/* @__PURE__ */ _ipv4(ZodIPv4, params));
  inst.ipv6 = (params) => inst.check(/* @__PURE__ */ _ipv6(ZodIPv6, params));
  inst.cidrv4 = (params) => inst.check(/* @__PURE__ */ _cidrv4(ZodCIDRv4, params));
  inst.cidrv6 = (params) => inst.check(/* @__PURE__ */ _cidrv6(ZodCIDRv6, params));
  inst.e164 = (params) => inst.check(/* @__PURE__ */ _e164(ZodE164, params));
  inst.datetime = (params) => inst.check(datetime(params));
  inst.date = (params) => inst.check(date(params));
  inst.time = (params) => inst.check(time(params));
  inst.duration = (params) => inst.check(duration(params));
});
function string(params) {
  return /* @__PURE__ */ _string(ZodString, params);
}
const ZodStringFormat = /* @__PURE__ */ $constructor("ZodStringFormat", (inst, def) => {
  $ZodStringFormat.init(inst, def);
  _ZodString.init(inst, def);
});
const ZodEmail = /* @__PURE__ */ $constructor("ZodEmail", (inst, def) => {
  $ZodEmail.init(inst, def);
  ZodStringFormat.init(inst, def);
});
const ZodGUID = /* @__PURE__ */ $constructor("ZodGUID", (inst, def) => {
  $ZodGUID.init(inst, def);
  ZodStringFormat.init(inst, def);
});
const ZodUUID = /* @__PURE__ */ $constructor("ZodUUID", (inst, def) => {
  $ZodUUID.init(inst, def);
  ZodStringFormat.init(inst, def);
});
const ZodURL = /* @__PURE__ */ $constructor("ZodURL", (inst, def) => {
  $ZodURL.init(inst, def);
  ZodStringFormat.init(inst, def);
});
const ZodEmoji = /* @__PURE__ */ $constructor("ZodEmoji", (inst, def) => {
  $ZodEmoji.init(inst, def);
  ZodStringFormat.init(inst, def);
});
const ZodNanoID = /* @__PURE__ */ $constructor("ZodNanoID", (inst, def) => {
  $ZodNanoID.init(inst, def);
  ZodStringFormat.init(inst, def);
});
const ZodCUID = /* @__PURE__ */ $constructor("ZodCUID", (inst, def) => {
  $ZodCUID.init(inst, def);
  ZodStringFormat.init(inst, def);
});
const ZodCUID2 = /* @__PURE__ */ $constructor("ZodCUID2", (inst, def) => {
  $ZodCUID2.init(inst, def);
  ZodStringFormat.init(inst, def);
});
const ZodULID = /* @__PURE__ */ $constructor("ZodULID", (inst, def) => {
  $ZodULID.init(inst, def);
  ZodStringFormat.init(inst, def);
});
const ZodXID = /* @__PURE__ */ $constructor("ZodXID", (inst, def) => {
  $ZodXID.init(inst, def);
  ZodStringFormat.init(inst, def);
});
const ZodKSUID = /* @__PURE__ */ $constructor("ZodKSUID", (inst, def) => {
  $ZodKSUID.init(inst, def);
  ZodStringFormat.init(inst, def);
});
const ZodIPv4 = /* @__PURE__ */ $constructor("ZodIPv4", (inst, def) => {
  $ZodIPv4.init(inst, def);
  ZodStringFormat.init(inst, def);
});
const ZodIPv6 = /* @__PURE__ */ $constructor("ZodIPv6", (inst, def) => {
  $ZodIPv6.init(inst, def);
  ZodStringFormat.init(inst, def);
});
const ZodCIDRv4 = /* @__PURE__ */ $constructor("ZodCIDRv4", (inst, def) => {
  $ZodCIDRv4.init(inst, def);
  ZodStringFormat.init(inst, def);
});
const ZodCIDRv6 = /* @__PURE__ */ $constructor("ZodCIDRv6", (inst, def) => {
  $ZodCIDRv6.init(inst, def);
  ZodStringFormat.init(inst, def);
});
const ZodBase64 = /* @__PURE__ */ $constructor("ZodBase64", (inst, def) => {
  $ZodBase64.init(inst, def);
  ZodStringFormat.init(inst, def);
});
const ZodBase64URL = /* @__PURE__ */ $constructor("ZodBase64URL", (inst, def) => {
  $ZodBase64URL.init(inst, def);
  ZodStringFormat.init(inst, def);
});
const ZodE164 = /* @__PURE__ */ $constructor("ZodE164", (inst, def) => {
  $ZodE164.init(inst, def);
  ZodStringFormat.init(inst, def);
});
const ZodJWT = /* @__PURE__ */ $constructor("ZodJWT", (inst, def) => {
  $ZodJWT.init(inst, def);
  ZodStringFormat.init(inst, def);
});
const ZodNumber = /* @__PURE__ */ $constructor("ZodNumber", (inst, def) => {
  $ZodNumber.init(inst, def);
  ZodType.init(inst, def);
  inst._zod.processJSONSchema = (ctx, json, params) => numberProcessor(inst, ctx, json);
  inst.gt = (value, params) => inst.check(/* @__PURE__ */ _gt(value, params));
  inst.gte = (value, params) => inst.check(/* @__PURE__ */ _gte(value, params));
  inst.min = (value, params) => inst.check(/* @__PURE__ */ _gte(value, params));
  inst.lt = (value, params) => inst.check(/* @__PURE__ */ _lt(value, params));
  inst.lte = (value, params) => inst.check(/* @__PURE__ */ _lte(value, params));
  inst.max = (value, params) => inst.check(/* @__PURE__ */ _lte(value, params));
  inst.int = (params) => inst.check(int(params));
  inst.safe = (params) => inst.check(int(params));
  inst.positive = (params) => inst.check(/* @__PURE__ */ _gt(0, params));
  inst.nonnegative = (params) => inst.check(/* @__PURE__ */ _gte(0, params));
  inst.negative = (params) => inst.check(/* @__PURE__ */ _lt(0, params));
  inst.nonpositive = (params) => inst.check(/* @__PURE__ */ _lte(0, params));
  inst.multipleOf = (value, params) => inst.check(/* @__PURE__ */ _multipleOf(value, params));
  inst.step = (value, params) => inst.check(/* @__PURE__ */ _multipleOf(value, params));
  inst.finite = () => inst;
  const bag = inst._zod.bag;
  inst.minValue = Math.max(bag.minimum ?? Number.NEGATIVE_INFINITY, bag.exclusiveMinimum ?? Number.NEGATIVE_INFINITY) ?? null;
  inst.maxValue = Math.min(bag.maximum ?? Number.POSITIVE_INFINITY, bag.exclusiveMaximum ?? Number.POSITIVE_INFINITY) ?? null;
  inst.isInt = (bag.format ?? "").includes("int") || Number.isSafeInteger(bag.multipleOf ?? 0.5);
  inst.isFinite = true;
  inst.format = bag.format ?? null;
});
function number(params) {
  return /* @__PURE__ */ _number(ZodNumber, params);
}
const ZodNumberFormat = /* @__PURE__ */ $constructor("ZodNumberFormat", (inst, def) => {
  $ZodNumberFormat.init(inst, def);
  ZodNumber.init(inst, def);
});
function int(params) {
  return /* @__PURE__ */ _int(ZodNumberFormat, params);
}
const ZodBoolean = /* @__PURE__ */ $constructor("ZodBoolean", (inst, def) => {
  $ZodBoolean.init(inst, def);
  ZodType.init(inst, def);
  inst._zod.processJSONSchema = (ctx, json, params) => booleanProcessor(inst, ctx, json);
});
function boolean(params) {
  return /* @__PURE__ */ _boolean(ZodBoolean, params);
}
const ZodUnknown = /* @__PURE__ */ $constructor("ZodUnknown", (inst, def) => {
  $ZodUnknown.init(inst, def);
  ZodType.init(inst, def);
  inst._zod.processJSONSchema = (ctx, json, params) => unknownProcessor();
});
function unknown() {
  return /* @__PURE__ */ _unknown(ZodUnknown);
}
const ZodNever = /* @__PURE__ */ $constructor("ZodNever", (inst, def) => {
  $ZodNever.init(inst, def);
  ZodType.init(inst, def);
  inst._zod.processJSONSchema = (ctx, json, params) => neverProcessor(inst, ctx, json);
});
function never(params) {
  return /* @__PURE__ */ _never(ZodNever, params);
}
const ZodArray = /* @__PURE__ */ $constructor("ZodArray", (inst, def) => {
  $ZodArray.init(inst, def);
  ZodType.init(inst, def);
  inst._zod.processJSONSchema = (ctx, json, params) => arrayProcessor(inst, ctx, json, params);
  inst.element = def.element;
  inst.min = (minLength, params) => inst.check(/* @__PURE__ */ _minLength(minLength, params));
  inst.nonempty = (params) => inst.check(/* @__PURE__ */ _minLength(1, params));
  inst.max = (maxLength, params) => inst.check(/* @__PURE__ */ _maxLength(maxLength, params));
  inst.length = (len, params) => inst.check(/* @__PURE__ */ _length(len, params));
  inst.unwrap = () => inst.element;
});
function array(element, params) {
  return /* @__PURE__ */ _array(ZodArray, element, params);
}
const ZodObject = /* @__PURE__ */ $constructor("ZodObject", (inst, def) => {
  $ZodObjectJIT.init(inst, def);
  ZodType.init(inst, def);
  inst._zod.processJSONSchema = (ctx, json, params) => objectProcessor(inst, ctx, json, params);
  defineLazy(inst, "shape", () => {
    return def.shape;
  });
  inst.keyof = () => _enum(Object.keys(inst._zod.def.shape));
  inst.catchall = (catchall) => inst.clone({ ...inst._zod.def, catchall });
  inst.passthrough = () => inst.clone({ ...inst._zod.def, catchall: unknown() });
  inst.loose = () => inst.clone({ ...inst._zod.def, catchall: unknown() });
  inst.strict = () => inst.clone({ ...inst._zod.def, catchall: never() });
  inst.strip = () => inst.clone({ ...inst._zod.def, catchall: void 0 });
  inst.extend = (incoming) => {
    return extend(inst, incoming);
  };
  inst.safeExtend = (incoming) => {
    return safeExtend(inst, incoming);
  };
  inst.merge = (other) => merge(inst, other);
  inst.pick = (mask) => pick(inst, mask);
  inst.omit = (mask) => omit(inst, mask);
  inst.partial = (...args) => partial(ZodOptional, inst, args[0]);
  inst.required = (...args) => required(ZodNonOptional, inst, args[0]);
});
function object(shape, params) {
  const def = {
    type: "object",
    shape: shape ?? {},
    ...normalizeParams(params)
  };
  return new ZodObject(def);
}
const ZodUnion = /* @__PURE__ */ $constructor("ZodUnion", (inst, def) => {
  $ZodUnion.init(inst, def);
  ZodType.init(inst, def);
  inst._zod.processJSONSchema = (ctx, json, params) => unionProcessor(inst, ctx, json, params);
  inst.options = def.options;
});
function union(options, params) {
  return new ZodUnion({
    type: "union",
    options,
    ...normalizeParams(params)
  });
}
const ZodDiscriminatedUnion = /* @__PURE__ */ $constructor("ZodDiscriminatedUnion", (inst, def) => {
  ZodUnion.init(inst, def);
  $ZodDiscriminatedUnion.init(inst, def);
});
function discriminatedUnion(discriminator, options, params) {
  return new ZodDiscriminatedUnion({
    type: "union",
    options,
    discriminator,
    ...normalizeParams(params)
  });
}
const ZodIntersection = /* @__PURE__ */ $constructor("ZodIntersection", (inst, def) => {
  $ZodIntersection.init(inst, def);
  ZodType.init(inst, def);
  inst._zod.processJSONSchema = (ctx, json, params) => intersectionProcessor(inst, ctx, json, params);
});
function intersection(left, right) {
  return new ZodIntersection({
    type: "intersection",
    left,
    right
  });
}
const ZodTuple = /* @__PURE__ */ $constructor("ZodTuple", (inst, def) => {
  $ZodTuple.init(inst, def);
  ZodType.init(inst, def);
  inst._zod.processJSONSchema = (ctx, json, params) => tupleProcessor(inst, ctx, json, params);
  inst.rest = (rest) => inst.clone({
    ...inst._zod.def,
    rest
  });
});
function tuple(items, _paramsOrRest, _params) {
  const hasRest = _paramsOrRest instanceof $ZodType;
  const params = hasRest ? _params : _paramsOrRest;
  const rest = hasRest ? _paramsOrRest : null;
  return new ZodTuple({
    type: "tuple",
    items,
    rest,
    ...normalizeParams(params)
  });
}
const ZodRecord = /* @__PURE__ */ $constructor("ZodRecord", (inst, def) => {
  $ZodRecord.init(inst, def);
  ZodType.init(inst, def);
  inst._zod.processJSONSchema = (ctx, json, params) => recordProcessor(inst, ctx, json, params);
  inst.keyType = def.keyType;
  inst.valueType = def.valueType;
});
function record(keyType, valueType, params) {
  return new ZodRecord({
    type: "record",
    keyType,
    valueType,
    ...normalizeParams(params)
  });
}
const ZodEnum = /* @__PURE__ */ $constructor("ZodEnum", (inst, def) => {
  $ZodEnum.init(inst, def);
  ZodType.init(inst, def);
  inst._zod.processJSONSchema = (ctx, json, params) => enumProcessor(inst, ctx, json);
  inst.enum = def.entries;
  inst.options = Object.values(def.entries);
  const keys = new Set(Object.keys(def.entries));
  inst.extract = (values, params) => {
    const newEntries = {};
    for (const value of values) {
      if (keys.has(value)) {
        newEntries[value] = def.entries[value];
      } else
        throw new Error(`Key ${value} not found in enum`);
    }
    return new ZodEnum({
      ...def,
      checks: [],
      ...normalizeParams(params),
      entries: newEntries
    });
  };
  inst.exclude = (values, params) => {
    const newEntries = { ...def.entries };
    for (const value of values) {
      if (keys.has(value)) {
        delete newEntries[value];
      } else
        throw new Error(`Key ${value} not found in enum`);
    }
    return new ZodEnum({
      ...def,
      checks: [],
      ...normalizeParams(params),
      entries: newEntries
    });
  };
});
function _enum(values, params) {
  const entries = Array.isArray(values) ? Object.fromEntries(values.map((v) => [v, v])) : values;
  return new ZodEnum({
    type: "enum",
    entries,
    ...normalizeParams(params)
  });
}
const ZodLiteral = /* @__PURE__ */ $constructor("ZodLiteral", (inst, def) => {
  $ZodLiteral.init(inst, def);
  ZodType.init(inst, def);
  inst._zod.processJSONSchema = (ctx, json, params) => literalProcessor(inst, ctx, json);
  inst.values = new Set(def.values);
  Object.defineProperty(inst, "value", {
    get() {
      if (def.values.length > 1) {
        throw new Error("This schema contains multiple valid literal values. Use `.values` instead.");
      }
      return def.values[0];
    }
  });
});
function literal(value, params) {
  return new ZodLiteral({
    type: "literal",
    values: Array.isArray(value) ? value : [value],
    ...normalizeParams(params)
  });
}
const ZodTransform = /* @__PURE__ */ $constructor("ZodTransform", (inst, def) => {
  $ZodTransform.init(inst, def);
  ZodType.init(inst, def);
  inst._zod.processJSONSchema = (ctx, json, params) => transformProcessor(inst, ctx);
  inst._zod.parse = (payload, _ctx) => {
    if (_ctx.direction === "backward") {
      throw new $ZodEncodeError(inst.constructor.name);
    }
    payload.addIssue = (issue$1) => {
      if (typeof issue$1 === "string") {
        payload.issues.push(issue(issue$1, payload.value, def));
      } else {
        const _issue = issue$1;
        if (_issue.fatal)
          _issue.continue = false;
        _issue.code ?? (_issue.code = "custom");
        _issue.input ?? (_issue.input = payload.value);
        _issue.inst ?? (_issue.inst = inst);
        payload.issues.push(issue(_issue));
      }
    };
    const output = def.transform(payload.value, payload);
    if (output instanceof Promise) {
      return output.then((output2) => {
        payload.value = output2;
        return payload;
      });
    }
    payload.value = output;
    return payload;
  };
});
function transform(fn) {
  return new ZodTransform({
    type: "transform",
    transform: fn
  });
}
const ZodOptional = /* @__PURE__ */ $constructor("ZodOptional", (inst, def) => {
  $ZodOptional.init(inst, def);
  ZodType.init(inst, def);
  inst._zod.processJSONSchema = (ctx, json, params) => optionalProcessor(inst, ctx, json, params);
  inst.unwrap = () => inst._zod.def.innerType;
});
function optional(innerType) {
  return new ZodOptional({
    type: "optional",
    innerType
  });
}
const ZodExactOptional = /* @__PURE__ */ $constructor("ZodExactOptional", (inst, def) => {
  $ZodExactOptional.init(inst, def);
  ZodType.init(inst, def);
  inst._zod.processJSONSchema = (ctx, json, params) => optionalProcessor(inst, ctx, json, params);
  inst.unwrap = () => inst._zod.def.innerType;
});
function exactOptional(innerType) {
  return new ZodExactOptional({
    type: "optional",
    innerType
  });
}
const ZodNullable = /* @__PURE__ */ $constructor("ZodNullable", (inst, def) => {
  $ZodNullable.init(inst, def);
  ZodType.init(inst, def);
  inst._zod.processJSONSchema = (ctx, json, params) => nullableProcessor(inst, ctx, json, params);
  inst.unwrap = () => inst._zod.def.innerType;
});
function nullable(innerType) {
  return new ZodNullable({
    type: "nullable",
    innerType
  });
}
const ZodDefault = /* @__PURE__ */ $constructor("ZodDefault", (inst, def) => {
  $ZodDefault.init(inst, def);
  ZodType.init(inst, def);
  inst._zod.processJSONSchema = (ctx, json, params) => defaultProcessor(inst, ctx, json, params);
  inst.unwrap = () => inst._zod.def.innerType;
  inst.removeDefault = inst.unwrap;
});
function _default(innerType, defaultValue) {
  return new ZodDefault({
    type: "default",
    innerType,
    get defaultValue() {
      return typeof defaultValue === "function" ? defaultValue() : shallowClone(defaultValue);
    }
  });
}
const ZodPrefault = /* @__PURE__ */ $constructor("ZodPrefault", (inst, def) => {
  $ZodPrefault.init(inst, def);
  ZodType.init(inst, def);
  inst._zod.processJSONSchema = (ctx, json, params) => prefaultProcessor(inst, ctx, json, params);
  inst.unwrap = () => inst._zod.def.innerType;
});
function prefault(innerType, defaultValue) {
  return new ZodPrefault({
    type: "prefault",
    innerType,
    get defaultValue() {
      return typeof defaultValue === "function" ? defaultValue() : shallowClone(defaultValue);
    }
  });
}
const ZodNonOptional = /* @__PURE__ */ $constructor("ZodNonOptional", (inst, def) => {
  $ZodNonOptional.init(inst, def);
  ZodType.init(inst, def);
  inst._zod.processJSONSchema = (ctx, json, params) => nonoptionalProcessor(inst, ctx, json, params);
  inst.unwrap = () => inst._zod.def.innerType;
});
function nonoptional(innerType, params) {
  return new ZodNonOptional({
    type: "nonoptional",
    innerType,
    ...normalizeParams(params)
  });
}
const ZodCatch = /* @__PURE__ */ $constructor("ZodCatch", (inst, def) => {
  $ZodCatch.init(inst, def);
  ZodType.init(inst, def);
  inst._zod.processJSONSchema = (ctx, json, params) => catchProcessor(inst, ctx, json, params);
  inst.unwrap = () => inst._zod.def.innerType;
  inst.removeCatch = inst.unwrap;
});
function _catch(innerType, catchValue) {
  return new ZodCatch({
    type: "catch",
    innerType,
    catchValue: typeof catchValue === "function" ? catchValue : () => catchValue
  });
}
const ZodPipe = /* @__PURE__ */ $constructor("ZodPipe", (inst, def) => {
  $ZodPipe.init(inst, def);
  ZodType.init(inst, def);
  inst._zod.processJSONSchema = (ctx, json, params) => pipeProcessor(inst, ctx, json, params);
  inst.in = def.in;
  inst.out = def.out;
});
function pipe(in_, out) {
  return new ZodPipe({
    type: "pipe",
    in: in_,
    out
    // ...util.normalizeParams(params),
  });
}
const ZodReadonly = /* @__PURE__ */ $constructor("ZodReadonly", (inst, def) => {
  $ZodReadonly.init(inst, def);
  ZodType.init(inst, def);
  inst._zod.processJSONSchema = (ctx, json, params) => readonlyProcessor(inst, ctx, json, params);
  inst.unwrap = () => inst._zod.def.innerType;
});
function readonly(innerType) {
  return new ZodReadonly({
    type: "readonly",
    innerType
  });
}
const ZodLazy = /* @__PURE__ */ $constructor("ZodLazy", (inst, def) => {
  $ZodLazy.init(inst, def);
  ZodType.init(inst, def);
  inst._zod.processJSONSchema = (ctx, json, params) => lazyProcessor(inst, ctx, json, params);
  inst.unwrap = () => inst._zod.def.getter();
});
function lazy(getter) {
  return new ZodLazy({
    type: "lazy",
    getter
  });
}
const ZodCustom = /* @__PURE__ */ $constructor("ZodCustom", (inst, def) => {
  $ZodCustom.init(inst, def);
  ZodType.init(inst, def);
  inst._zod.processJSONSchema = (ctx, json, params) => customProcessor(inst, ctx);
});
function refine(fn, _params = {}) {
  return /* @__PURE__ */ _refine(ZodCustom, fn, _params);
}
function superRefine(fn) {
  return /* @__PURE__ */ _superRefine(fn);
}
const GeometrySchema = object({
  x: number(),
  y: number(),
  width: number().positive(),
  height: number().positive()
});
const WindowStateSchema = object({
  id: string().min(1),
  workspaceIds: array(string()),
  geometry: GeometrySchema,
  isActive: boolean()
});
const PanelLayoutLeafSchema = object({ type: literal("leaf"), panelId: string() });
const PanelLayoutSplitSchema = lazy(
  () => object({
    type: literal("split"),
    direction: _enum(["horizontal", "vertical"]),
    ratio: number().min(0).max(1),
    children: tuple([PanelLayoutTreeSchema, PanelLayoutTreeSchema])
  })
);
const PanelLayoutTreeSchema = union([PanelLayoutLeafSchema, PanelLayoutSplitSchema]);
const StatusEntrySchema = object({
  key: string(),
  label: string(),
  icon: string().optional(),
  color: string().optional()
});
const WorkspaceStateSchema = object({
  id: string().min(1),
  windowId: string().min(1),
  name: string(),
  color: string().optional(),
  panelLayout: PanelLayoutTreeSchema,
  agentPids: record(string(), number()),
  statusEntries: array(StatusEntrySchema),
  unreadCount: number().int().min(0),
  isPinned: boolean(),
  remoteSession: object({
    host: string(),
    port: number(),
    status: _enum(["connecting", "connected", "disconnected", "error"])
  }).optional()
});
const PanelTypeEnum = _enum(["terminal", "browser", "markdown"]);
const PanelStateSchema = object({
  id: string().min(1),
  workspaceId: string().min(1),
  panelType: PanelTypeEnum,
  surfaceIds: array(string()),
  activeSurfaceId: string(),
  isZoomed: boolean()
});
const SurfaceStateSchema = object({
  id: string().min(1),
  panelId: string().min(1),
  surfaceType: PanelTypeEnum,
  title: string(),
  terminal: object({ pid: number(), cwd: string(), shell: string() }).optional(),
  browser: object({ url: string(), profileId: string(), isLoading: boolean() }).optional(),
  markdown: object({ filePath: string() }).optional()
});
const AgentTypeEnum = _enum(["claude", "codex", "gemini", "opencode"]);
const AgentStatusEnum = _enum(["running", "idle", "needs_input"]);
const AgentSessionStateSchema = object({
  sessionId: string().min(1),
  agentType: AgentTypeEnum,
  workspaceId: string(),
  surfaceId: string(),
  status: AgentStatusEnum,
  statusIcon: string(),
  statusColor: string(),
  pid: number().optional(),
  lastActivity: number()
});
const NotificationStateSchema = object({
  id: string().min(1),
  workspaceId: string().optional(),
  surfaceId: string().optional(),
  title: string(),
  subtitle: string().optional(),
  body: string().optional(),
  createdAt: number(),
  isRead: boolean()
});
const SettingsStateSchema = object({
  appearance: object({
    theme: _enum(["system", "light", "dark"]),
    language: _enum(["system", "en", "ko", "ja"]),
    iconMode: _enum(["auto", "colorful", "monochrome"])
  }),
  terminal: object({
    defaultShell: _enum(["powershell", "cmd", "wsl", "git-bash"]),
    fontSize: number().int().min(6).max(72),
    fontFamily: string(),
    themeName: string(),
    cursorStyle: _enum(["block", "underline", "bar"])
  }),
  browser: object({
    searchEngine: _enum(["google", "duckduckgo", "bing", "kagi", "startpage"]),
    searchSuggestions: boolean(),
    httpAllowlist: array(string()),
    externalUrlPatterns: array(string())
  }),
  socket: object({
    mode: _enum(["off", "cmux-only", "automation", "password", "allow-all"]),
    port: number().int().min(1024).max(65535)
  }),
  agents: object({
    claudeHooksEnabled: boolean(),
    codexHooksEnabled: boolean(),
    geminiHooksEnabled: boolean(),
    orchestrationMode: _enum(["auto", "claude-teams", "self-managed"])
  }),
  telemetry: object({ enabled: boolean() }),
  updates: object({ autoCheck: boolean(), channel: _enum(["stable", "nightly"]) }),
  accessibility: object({ screenReaderMode: boolean(), reducedMotion: boolean() }),
  bridge: object({
    enabled: boolean(),
    basePath: string(),
    heartbeatIntervalSec: number().int().min(5),
    pollIntervalSec: number().int().min(1)
  })
});
const FocusStateSchema = object({
  activeWindowId: string().nullable(),
  activeWorkspaceId: string().nullable(),
  activePanelId: string().nullable(),
  activeSurfaceId: string().nullable(),
  focusTarget: _enum(["terminal", "browser_webview", "browser_omnibar", "browser_find", "terminal_find"]).nullable()
});
const AppStateSchema = object({
  windows: array(WindowStateSchema),
  workspaces: array(WorkspaceStateSchema),
  panels: array(PanelStateSchema),
  surfaces: array(SurfaceStateSchema),
  agents: array(AgentSessionStateSchema),
  notifications: array(NotificationStateSchema),
  settings: SettingsStateSchema,
  shortcuts: object({ shortcuts: record(string(), string()) }),
  focus: FocusStateSchema
});
object({
  version: number().int().positive(),
  state: AppStateSchema
});
const WindowCreateAction = object({
  type: literal("window.create"),
  payload: object({ geometry: GeometrySchema.optional() })
});
const WindowCloseAction = object({
  type: literal("window.close"),
  payload: object({ windowId: string() })
});
const WorkspaceCreateAction = object({
  type: literal("workspace.create"),
  payload: object({
    windowId: string(),
    name: string().optional(),
    cwd: string().optional()
  })
});
const WorkspaceCloseAction = object({
  type: literal("workspace.close"),
  payload: object({ workspaceId: string() })
});
const WorkspaceSelectAction = object({
  type: literal("workspace.select"),
  payload: object({ workspaceId: string() })
});
const WorkspaceRenameAction = object({
  type: literal("workspace.rename"),
  payload: object({ workspaceId: string(), name: string() })
});
const PanelSplitAction = object({
  type: literal("panel.split"),
  payload: object({
    panelId: string(),
    direction: _enum(["horizontal", "vertical"]),
    newPanelType: PanelTypeEnum,
    url: string().optional(),
    filePath: string().optional()
  })
});
const PanelCloseAction = object({
  type: literal("panel.close"),
  payload: object({ panelId: string() })
});
const PanelFocusAction = object({
  type: literal("panel.focus"),
  payload: object({ panelId: string() })
});
const PanelResizeAction = object({
  type: literal("panel.resize"),
  payload: object({ panelId: string(), ratio: number().min(0).max(1) })
});
const SurfaceCreateAction = object({
  type: literal("surface.create"),
  payload: object({ panelId: string(), surfaceType: PanelTypeEnum })
});
const SurfaceCloseAction = object({
  type: literal("surface.close"),
  payload: object({ surfaceId: string() })
});
const SurfaceFocusAction = object({
  type: literal("surface.focus"),
  payload: object({ surfaceId: string() })
});
const SurfaceSendTextAction = object({
  type: literal("surface.send_text"),
  payload: object({ surfaceId: string(), text: string() })
});
const SurfaceUpdateMetaAction = object({
  type: literal("surface.update_meta"),
  payload: object({
    surfaceId: string(),
    title: string().optional(),
    pendingCommand: string().nullable().optional(),
    terminal: object({
      cwd: string().optional(),
      gitBranch: string().optional(),
      gitDirty: boolean().optional(),
      exitCode: number().optional()
    }).optional(),
    browser: object({
      url: string().optional(),
      isLoading: boolean().optional()
    }).optional()
  })
});
const AgentSpawnAction = object({
  type: literal("agent.spawn"),
  payload: object({
    agentType: _enum(["claude", "codex", "gemini", "opencode"]),
    workspaceId: string(),
    task: string().optional(),
    cwd: string().optional()
  })
});
const AgentSessionStartAction = object({
  type: literal("agent.session_start"),
  payload: object({
    sessionId: string(),
    agentType: _enum(["claude", "codex", "gemini", "opencode"]),
    workspaceId: string(),
    surfaceId: string(),
    pid: number().optional()
  })
});
const AgentStatusUpdateAction = object({
  type: literal("agent.status_update"),
  payload: object({
    sessionId: string(),
    status: _enum(["running", "idle", "needs_input", "done", "error"]),
    icon: string().optional(),
    color: string().optional()
  })
});
const AgentSessionEndAction = object({
  type: literal("agent.session_end"),
  payload: object({ sessionId: string() })
});
const NotificationCreateAction = object({
  type: literal("notification.create"),
  payload: object({
    title: string(),
    subtitle: string().optional(),
    body: string().optional(),
    workspaceId: string().optional(),
    surfaceId: string().optional()
  })
});
const NotificationClearAction = object({
  type: literal("notification.clear"),
  payload: object({ workspaceId: string().optional() })
});
const PanelZoomAction = object({
  type: literal("panel.zoom"),
  payload: object({ panelId: string() })
});
const PanelSwapAction = object({
  type: literal("panel.swap"),
  payload: object({ panelId1: string(), panelId2: string() })
});
const PanelMoveAction = object({
  type: literal("panel.move"),
  payload: object({
    sourcePanelId: string(),
    targetPanelId: string(),
    direction: _enum(["left", "right", "top", "bottom"])
  })
});
const SurfaceReorderAction = object({
  type: literal("surface.reorder"),
  payload: object({
    surfaceId: string(),
    panelId: string(),
    newIndex: number().int().min(0)
  })
});
const WorkspaceReorderAction = object({
  type: literal("workspace.reorder"),
  payload: object({
    workspaceId: string(),
    windowId: string(),
    newIndex: number().int().min(0)
  })
});
const WorkspaceSetLayoutAction = object({
  type: literal("workspace.set_layout"),
  payload: object({
    workspaceId: string(),
    panelLayout: PanelLayoutTreeSchema
  })
});
const FocusUpdateAction = object({
  type: literal("focus.update"),
  payload: object({
    activeWindowId: string().nullable().optional(),
    activeWorkspaceId: string().nullable().optional(),
    activePanelId: string().nullable().optional(),
    activeSurfaceId: string().nullable().optional(),
    focusTarget: _enum(["terminal", "browser_webview", "browser_omnibar", "browser_find", "terminal_find"]).nullable().optional()
  })
});
const SettingsUpdateAction = object({
  type: literal("settings.update"),
  payload: record(string(), unknown())
});
const ActionSchema = discriminatedUnion("type", [
  WindowCreateAction,
  WindowCloseAction,
  WorkspaceCreateAction,
  WorkspaceCloseAction,
  WorkspaceSelectAction,
  WorkspaceRenameAction,
  WorkspaceReorderAction,
  WorkspaceSetLayoutAction,
  PanelSplitAction,
  PanelCloseAction,
  PanelFocusAction,
  PanelResizeAction,
  PanelZoomAction,
  PanelSwapAction,
  PanelMoveAction,
  SurfaceCreateAction,
  SurfaceCloseAction,
  SurfaceFocusAction,
  SurfaceSendTextAction,
  SurfaceReorderAction,
  SurfaceUpdateMetaAction,
  AgentSpawnAction,
  AgentSessionStartAction,
  AgentStatusUpdateAction,
  AgentSessionEndAction,
  NotificationCreateAction,
  NotificationClearAction,
  FocusUpdateAction,
  SettingsUpdateAction
]);
function createDefaultState() {
  return {
    windows: [],
    workspaces: [],
    panels: [],
    surfaces: [],
    agents: [],
    notifications: [],
    settings: structuredClone(DEFAULT_SETTINGS),
    shortcuts: { shortcuts: {} },
    focus: {
      activeWindowId: null,
      activeWorkspaceId: null,
      activePanelId: null,
      activeSurfaceId: null,
      focusTarget: null
    }
  };
}
function findLeaf(tree, panelId) {
  if (tree.type === "leaf") {
    return tree.panelId === panelId ? tree : null;
  }
  return findLeaf(tree.children[0], panelId) ?? findLeaf(tree.children[1], panelId);
}
function replaceLeaf(tree, panelId, replacement) {
  if (tree.type === "leaf") {
    return tree.panelId === panelId ? replacement : tree;
  }
  return {
    ...tree,
    children: [
      replaceLeaf(tree.children[0], panelId, replacement),
      replaceLeaf(tree.children[1], panelId, replacement)
    ]
  };
}
function updateRatioForPanel(tree, panelId, newRatio) {
  if (tree.type === "leaf") return tree;
  const clamped = Math.max(0.1, Math.min(0.9, newRatio));
  const isDirectChild = tree.children.some((c) => c.type === "leaf" && c.panelId === panelId);
  if (isDirectChild) {
    return { ...tree, ratio: clamped };
  }
  return {
    ...tree,
    children: [
      updateRatioForPanel(tree.children[0], panelId, newRatio),
      updateRatioForPanel(tree.children[1], panelId, newRatio)
    ]
  };
}
function removeLeaf(tree, panelId) {
  if (tree.type === "leaf") {
    return tree.panelId === panelId ? null : tree;
  }
  const [left, right] = tree.children;
  if (left.type === "leaf" && left.panelId === panelId) return right;
  if (right.type === "leaf" && right.panelId === panelId) return left;
  const newLeft = removeLeaf(left, panelId);
  if (newLeft !== left) return { ...tree, children: [newLeft ?? right, right] };
  const newRight = removeLeaf(right, panelId);
  if (newRight !== right) return { ...tree, children: [left, newRight ?? left] };
  return tree;
}
class AppStateStore extends node_events.EventEmitter {
  constructor(initialState2) {
    super();
    this.history = [];
    this.middlewares = [];
    this.state = initialState2 ?? createDefaultState();
  }
  getState() {
    return this.state;
  }
  getHistory() {
    return this.history;
  }
  use(mw) {
    this.middlewares.push(mw);
  }
  // BUG-14: 세션 복원 시 고아 워크스페이스를 새 윈도우에 입양
  adoptOrphanWorkspaces(windowId) {
    this.state = produce(this.state, (draft) => {
      const win = draft.windows.find((w) => w.id === windowId);
      if (!win) return;
      for (const ws of draft.workspaces) {
        if (!ws.windowId || !draft.windows.some((w) => w.id === ws.windowId)) {
          ws.windowId = windowId;
          if (!win.workspaceIds.includes(ws.id)) {
            win.workspaceIds.push(ws.id);
          }
        }
      }
    });
    this.emit("change", { type: "session.restore" });
  }
  dispatch(rawAction) {
    var _a3, _b, _c, _d;
    const parsed = ActionSchema.safeParse(rawAction);
    if (!parsed.success) return { ok: false, error: parsed.error.message };
    const action = parsed.data;
    for (const mw of this.middlewares) {
      if (mw.beforeMutation) {
        const result = mw.beforeMutation(action, this.state);
        if (result.abort) return { ok: false, error: result.reason ?? "Aborted by middleware" };
      }
    }
    const prevState = this.state;
    try {
      if (action.type === "surface.send_text") {
        this.emit("side-effect", {
          type: "pty-write",
          surfaceId: action.payload.surfaceId,
          text: action.payload.text
        });
        for (const mw of this.middlewares) {
          try {
            (_a3 = mw.afterMutation) == null ? void 0 : _a3.call(mw, action, prevState, prevState);
          } catch (err) {
            console.error("[Middleware] afterMutation error:", err);
          }
        }
        for (const mw of this.middlewares) {
          try {
            (_b = mw.post) == null ? void 0 : _b.call(mw, action, prevState, prevState);
          } catch (err) {
            console.error("[Middleware] post error:", err);
          }
        }
        return { ok: true };
      }
      this.state = produce(this.state, (draft) => {
        this.applyAction(draft, action);
      });
      this.history.push({ action, timestamp: Date.now() });
      if (this.history.length > STATE_HISTORY_MAX) this.history.shift();
      for (const mw of this.middlewares) {
        try {
          (_c = mw.afterMutation) == null ? void 0 : _c.call(mw, action, prevState, this.state);
        } catch (err) {
          console.error("[Middleware] afterMutation error:", err);
        }
      }
      for (const mw of this.middlewares) {
        try {
          (_d = mw.post) == null ? void 0 : _d.call(mw, action, prevState, this.state);
        } catch (err) {
          console.error("[Middleware] post error:", err);
        }
      }
      this.emit("change", action);
      return { ok: true };
    } catch (err) {
      return { ok: false, error: err instanceof Error ? err.message : String(err) };
    }
  }
  // GAP-4: monotonically increasing pane index — survives panel close/reorder
  nextPaneIndex(draft) {
    let max = -1;
    for (const p of draft.panels) {
      if (p.paneIndex !== void 0 && p.paneIndex > max) max = p.paneIndex;
    }
    return max + 1;
  }
  applyAction(draft, action) {
    var _a3, _b;
    switch (action.type) {
      // BUG-2: window.create / window.close
      case "window.create": {
        const id = crypto$1.randomUUID();
        const geo = action.payload.geometry ?? { x: 100, y: 100, width: 1200, height: 800 };
        draft.windows.push({ id, workspaceIds: [], geometry: geo, isActive: true });
        draft.focus.activeWindowId = id;
        break;
      }
      case "window.close": {
        const idx = draft.windows.findIndex((w) => w.id === action.payload.windowId);
        if (idx === -1) break;
        const win = draft.windows[idx];
        for (const wsId of win.workspaceIds) {
          draft.panels = draft.panels.filter((p) => p.workspaceId !== wsId);
          draft.surfaces = draft.surfaces.filter(
            (s) => draft.panels.some((p) => p.id === s.panelId)
          );
        }
        draft.workspaces = draft.workspaces.filter((ws) => !win.workspaceIds.includes(ws.id));
        draft.windows.splice(idx, 1);
        if (draft.focus.activeWindowId === action.payload.windowId) {
          draft.focus.activeWindowId = ((_a3 = draft.windows[0]) == null ? void 0 : _a3.id) ?? null;
        }
        break;
      }
      case "workspace.create": {
        const id = crypto$1.randomUUID();
        const panelId = crypto$1.randomUUID();
        const surfaceId = crypto$1.randomUUID();
        draft.workspaces.push({
          id,
          windowId: action.payload.windowId,
          name: action.payload.name ?? "New Workspace",
          panelLayout: { type: "leaf", panelId },
          agentPids: {},
          statusEntries: [],
          unreadCount: 0,
          isPinned: false
        });
        draft.panels.push({
          id: panelId,
          workspaceId: id,
          panelType: "terminal",
          surfaceIds: [surfaceId],
          activeSurfaceId: surfaceId,
          isZoomed: false,
          paneIndex: this.nextPaneIndex(draft)
        });
        const isFirstWorkspace = draft.workspaces.length === 1;
        const claudeCmd = isFirstWorkspace ? "claude --dangerously-skip-permissions\r" : void 0;
        draft.surfaces.push({
          id: surfaceId,
          panelId,
          surfaceType: "terminal",
          title: claudeCmd ? "🧠 Claude" : "Terminal",
          pendingCommand: claudeCmd
        });
        const win = draft.windows.find((w) => w.id === action.payload.windowId);
        if (win) win.workspaceIds.push(id);
        draft.focus.activeWorkspaceId = id;
        draft.focus.activeWindowId = action.payload.windowId;
        draft.focus.activePanelId = panelId;
        draft.focus.activeSurfaceId = surfaceId;
        break;
      }
      case "workspace.close": {
        const wsIdx = draft.workspaces.findIndex((w) => w.id === action.payload.workspaceId);
        if (wsIdx === -1) break;
        draft.panels = draft.panels.filter((p) => p.workspaceId !== action.payload.workspaceId);
        draft.surfaces = draft.surfaces.filter((s) => draft.panels.some((p) => p.id === s.panelId));
        draft.workspaces.splice(wsIdx, 1);
        for (const win of draft.windows) {
          win.workspaceIds = win.workspaceIds.filter((id) => id !== action.payload.workspaceId);
        }
        if (draft.focus.activeWorkspaceId === action.payload.workspaceId) {
          draft.focus.activeWorkspaceId = ((_b = draft.workspaces[0]) == null ? void 0 : _b.id) ?? null;
        }
        break;
      }
      case "workspace.select": {
        draft.focus.activeWorkspaceId = action.payload.workspaceId;
        const ws = draft.workspaces.find((w) => w.id === action.payload.workspaceId);
        if (ws) {
          draft.focus.activeWindowId = ws.windowId;
          const firstPanel = draft.panels.find((p) => p.workspaceId === ws.id);
          if (firstPanel) {
            draft.focus.activePanelId = firstPanel.id;
            draft.focus.activeSurfaceId = firstPanel.activeSurfaceId || firstPanel.surfaceIds[0] || null;
          }
        }
        break;
      }
      case "workspace.rename": {
        const ws = draft.workspaces.find((w) => w.id === action.payload.workspaceId);
        if (ws) ws.name = action.payload.name;
        break;
      }
      case "panel.focus": {
        draft.focus.activePanelId = action.payload.panelId;
        break;
      }
      case "panel.close": {
        const panelId = action.payload.panelId;
        const idx = draft.panels.findIndex((p) => p.id === panelId);
        if (idx === -1) break;
        draft.surfaces = draft.surfaces.filter((s) => s.panelId !== panelId);
        draft.panels.splice(idx, 1);
        const ws = draft.workspaces.find((w) => findLeaf(w.panelLayout, panelId) !== null);
        if (ws) {
          const newLayout = removeLeaf(ws.panelLayout, panelId);
          if (newLayout) ws.panelLayout = newLayout;
        }
        break;
      }
      case "panel.split": {
        const { panelId, direction, newPanelType, url } = action.payload;
        const ws = draft.workspaces.find((w) => findLeaf(w.panelLayout, panelId) !== null);
        if (!ws) break;
        const newPanelId = crypto$1.randomUUID();
        const newSurfaceId = crypto$1.randomUUID();
        draft.panels.push({
          id: newPanelId,
          workspaceId: ws.id,
          panelType: newPanelType,
          surfaceIds: [newSurfaceId],
          activeSurfaceId: newSurfaceId,
          isZoomed: false,
          paneIndex: this.nextPaneIndex(draft)
        });
        const surface = {
          id: newSurfaceId,
          panelId: newPanelId,
          surfaceType: newPanelType,
          title: newPanelType === "terminal" ? "Terminal" : "New Tab"
        };
        if (newPanelType === "browser" && url) {
          surface.browser = { url, profileId: "default", isLoading: false };
          surface.title = new URL(url).hostname;
        }
        if (newPanelType === "markdown" && action.payload.filePath) {
          surface.markdown = { filePath: action.payload.filePath };
          surface.title = action.payload.filePath.split(/[\\/]/).pop() || "Markdown";
        }
        draft.surfaces.push(surface);
        const newSplit = {
          type: "split",
          direction,
          ratio: 0.5,
          children: [
            { type: "leaf", panelId },
            { type: "leaf", panelId: newPanelId }
          ]
        };
        ws.panelLayout = replaceLeaf(ws.panelLayout, panelId, newSplit);
        break;
      }
      case "panel.resize": {
        const { panelId, ratio } = action.payload;
        const ws = draft.workspaces.find((w) => findLeaf(w.panelLayout, panelId) !== null);
        if (!ws) break;
        ws.panelLayout = updateRatioForPanel(ws.panelLayout, panelId, ratio);
        break;
      }
      case "panel.zoom": {
        const panel = draft.panels.find((p) => p.id === action.payload.panelId);
        if (panel) panel.isZoomed = !panel.isZoomed;
        break;
      }
      case "panel.swap": {
        const { panelId1, panelId2 } = action.payload;
        if (panelId1 === panelId2) break;
        const p1 = draft.panels.find((p) => p.id === panelId1);
        const p2 = draft.panels.find((p) => p.id === panelId2);
        if (!p1 || !p2) break;
        const tempSurfaceIds = [...p1.surfaceIds];
        const tempActiveSurface = p1.activeSurfaceId;
        p1.surfaceIds = [...p2.surfaceIds];
        p1.activeSurfaceId = p2.activeSurfaceId;
        p2.surfaceIds = tempSurfaceIds;
        p2.activeSurfaceId = tempActiveSurface;
        for (const s of draft.surfaces) {
          if (tempSurfaceIds.includes(s.id)) s.panelId = panelId2;
          else if (p2.surfaceIds.includes(s.id)) s.panelId = panelId1;
        }
        break;
      }
      case "panel.move": {
        const { sourcePanelId, targetPanelId, direction } = action.payload;
        if (sourcePanelId === targetPanelId) break;
        const ws = draft.workspaces.find(
          (w) => findLeaf(w.panelLayout, sourcePanelId) !== null && findLeaf(w.panelLayout, targetPanelId) !== null
        );
        if (!ws) break;
        const layoutAfterRemove = removeLeaf(ws.panelLayout, sourcePanelId);
        if (!layoutAfterRemove) break;
        const splitDirection = direction === "left" || direction === "right" ? "horizontal" : "vertical";
        const sourceFirst = direction === "left" || direction === "top";
        const newSplit = {
          type: "split",
          direction: splitDirection,
          ratio: 0.5,
          children: sourceFirst ? [{ type: "leaf", panelId: sourcePanelId }, { type: "leaf", panelId: targetPanelId }] : [{ type: "leaf", panelId: targetPanelId }, { type: "leaf", panelId: sourcePanelId }]
        };
        ws.panelLayout = replaceLeaf(layoutAfterRemove, targetPanelId, newSplit);
        break;
      }
      case "surface.create": {
        const newId = crypto$1.randomUUID();
        const panel = draft.panels.find((p) => p.id === action.payload.panelId);
        if (!panel) break;
        draft.surfaces.push({
          id: newId,
          panelId: action.payload.panelId,
          surfaceType: action.payload.surfaceType,
          title: action.payload.surfaceType === "terminal" ? "Terminal" : "New Tab"
        });
        panel.surfaceIds.push(newId);
        panel.activeSurfaceId = newId;
        break;
      }
      case "surface.close": {
        const si = draft.surfaces.findIndex((s) => s.id === action.payload.surfaceId);
        if (si === -1) break;
        const surf = draft.surfaces[si];
        const panel = draft.panels.find((p) => p.id === surf.panelId);
        if (panel) {
          panel.surfaceIds = panel.surfaceIds.filter((id) => id !== action.payload.surfaceId);
          if (panel.activeSurfaceId === action.payload.surfaceId)
            panel.activeSurfaceId = panel.surfaceIds[0] ?? "";
          if (panel.surfaceIds.length === 0) {
            const pIdx = draft.panels.findIndex((p2) => p2.id === panel.id);
            if (pIdx !== -1) draft.panels.splice(pIdx, 1);
            const ws = draft.workspaces.find((w) => findLeaf(w.panelLayout, panel.id) !== null);
            if (ws) {
              const newLayout = removeLeaf(ws.panelLayout, panel.id);
              if (newLayout) ws.panelLayout = newLayout;
            }
          }
        }
        draft.surfaces.splice(si, 1);
        draft.agents = draft.agents.filter(
          (a) => draft.surfaces.some((sf) => sf.id === a.surfaceId)
        );
        break;
      }
      case "surface.focus": {
        draft.focus.activeSurfaceId = action.payload.surfaceId;
        const s = draft.surfaces.find((sf) => sf.id === action.payload.surfaceId);
        if (s) {
          draft.focus.activePanelId = s.panelId;
          const p = draft.panels.find((pp) => pp.id === s.panelId);
          if (p) p.activeSurfaceId = action.payload.surfaceId;
        }
        break;
      }
      case "surface.reorder": {
        const panel = draft.panels.find((p) => p.id === action.payload.panelId);
        if (!panel) break;
        const oldIndex = panel.surfaceIds.indexOf(action.payload.surfaceId);
        if (oldIndex === -1) break;
        panel.surfaceIds.splice(oldIndex, 1);
        panel.surfaceIds.splice(action.payload.newIndex, 0, action.payload.surfaceId);
        break;
      }
      case "workspace.reorder": {
        const win = draft.windows.find((w) => w.id === action.payload.windowId);
        if (!win) break;
        const oldIdx = win.workspaceIds.indexOf(action.payload.workspaceId);
        if (oldIdx === -1) break;
        win.workspaceIds.splice(oldIdx, 1);
        win.workspaceIds.splice(action.payload.newIndex, 0, action.payload.workspaceId);
        break;
      }
      case "workspace.set_layout": {
        const ws = draft.workspaces.find((w) => w.id === action.payload.workspaceId);
        if (ws && action.payload.panelLayout) {
          ws.panelLayout = action.payload.panelLayout;
        }
        break;
      }
      case "surface.send_text":
        break;
      // side-effect only, handled above dispatch
      case "agent.spawn": {
        const { agentType, workspaceId, task, cwd } = action.payload;
        const ws = draft.workspaces.find((w) => w.id === workspaceId);
        if (!ws) break;
        const agentIcons = {
          claude: "🧠",
          gemini: "💎",
          codex: "🤖",
          opencode: "🔧"
        };
        const agentIcon = agentIcons[agentType] || "⚡";
        const agentDisplayName = agentType.charAt(0).toUpperCase() + agentType.slice(1);
        const newPanelId = crypto$1.randomUUID();
        const newSurfaceId = crypto$1.randomUUID();
        const spawnedPaneIndex = this.nextPaneIndex(draft);
        draft.panels.push({
          id: newPanelId,
          workspaceId,
          panelType: "terminal",
          surfaceIds: [newSurfaceId],
          activeSurfaceId: newSurfaceId,
          isZoomed: false,
          paneIndex: spawnedPaneIndex
        });
        const teamName = workspaceId;
        const agentName = `${agentType}-${spawnedPaneIndex}`;
        const teamArgs = `--team-name "${teamName}" --agent-name "${agentName}"`;
        const safeTask = task ? task.replace(/[\r\n]+/g, " ").replace(/"/g, '\\"').trim() : "";
        let agentCmd;
        if (agentType === "gemini") {
          agentCmd = safeTask ? `gemini -i "${safeTask}" -y\r` : `gemini -y\r`;
        } else if (agentType === "codex") {
          agentCmd = safeTask ? `codex --full-auto --no-alt-screen "${safeTask}"\r` : `codex --full-auto --no-alt-screen\r`;
        } else {
          agentCmd = safeTask ? `${agentType} ${teamArgs} "${safeTask}"\r` : `${agentType} ${teamArgs}\r`;
        }
        const cmd = cwd ? `cd "${cwd.replace(/\\/g, "/")}"\r__DELAY__${agentCmd}` : agentCmd;
        draft.surfaces.push({
          id: newSurfaceId,
          panelId: newPanelId,
          surfaceType: "terminal",
          title: cwd ? `${agentIcon} ${agentDisplayName} · ${cwd.split(/[\\/]/).pop()}` : `${agentIcon} ${agentDisplayName}`,
          pendingCommand: cmd
        });
        ws.panelLayout = {
          type: "split",
          direction: "horizontal",
          ratio: 0.5,
          children: [ws.panelLayout, { type: "leaf", panelId: newPanelId }]
        };
        draft.agents.push({
          sessionId: crypto$1.randomUUID(),
          agentType,
          workspaceId,
          surfaceId: newSurfaceId,
          status: "running",
          statusIcon: "⚡",
          statusColor: "#4C8DFF",
          lastActivity: Date.now()
        });
        break;
      }
      case "agent.session_start": {
        draft.agents.push({
          sessionId: action.payload.sessionId,
          agentType: action.payload.agentType,
          workspaceId: action.payload.workspaceId,
          surfaceId: action.payload.surfaceId,
          status: "running",
          statusIcon: "⚡",
          statusColor: "blue",
          pid: action.payload.pid,
          lastActivity: Date.now()
        });
        break;
      }
      case "agent.status_update": {
        const agent = draft.agents.find((a) => a.sessionId === action.payload.sessionId);
        if (agent) {
          agent.status = action.payload.status;
          if (action.payload.icon) agent.statusIcon = action.payload.icon;
          if (action.payload.color) agent.statusColor = action.payload.color;
          agent.lastActivity = Date.now();
        }
        break;
      }
      case "agent.session_end": {
        draft.agents = draft.agents.filter((a) => a.sessionId !== action.payload.sessionId);
        break;
      }
      case "notification.create": {
        draft.notifications.push({
          id: crypto$1.randomUUID(),
          title: action.payload.title,
          subtitle: action.payload.subtitle,
          body: action.payload.body,
          workspaceId: action.payload.workspaceId,
          surfaceId: action.payload.surfaceId,
          createdAt: Date.now(),
          isRead: false
        });
        break;
      }
      case "notification.clear": {
        if (action.payload.workspaceId) {
          draft.notifications = draft.notifications.filter(
            (n) => n.workspaceId !== action.payload.workspaceId
          );
        } else {
          draft.notifications = [];
        }
        break;
      }
      case "focus.update": {
        const p = action.payload;
        if (p.activeWindowId !== void 0) draft.focus.activeWindowId = p.activeWindowId;
        if (p.activeWorkspaceId !== void 0) draft.focus.activeWorkspaceId = p.activeWorkspaceId;
        if (p.activePanelId !== void 0) draft.focus.activePanelId = p.activePanelId;
        if (p.activeSurfaceId !== void 0) draft.focus.activeSurfaceId = p.activeSurfaceId;
        if (p.focusTarget !== void 0) draft.focus.focusTarget = p.focusTarget;
        break;
      }
      case "surface.update_meta": {
        const surface = draft.surfaces.find((s) => s.id === action.payload.surfaceId);
        if (!surface) break;
        if (action.payload.title !== void 0) surface.title = action.payload.title;
        if (action.payload.pendingCommand !== void 0) {
          surface.pendingCommand = action.payload.pendingCommand ?? void 0;
        }
        if (action.payload.terminal) {
          const t = action.payload.terminal;
          if (!surface.terminal) surface.terminal = { pid: 0, cwd: "", shell: "" };
          if (t.cwd !== void 0) surface.terminal.cwd = t.cwd;
          if (t.gitBranch !== void 0) surface.terminal.gitBranch = t.gitBranch;
          if (t.gitDirty !== void 0) surface.terminal.gitDirty = t.gitDirty;
          if (t.exitCode !== void 0) surface.terminal.exitCode = t.exitCode;
        }
        if (action.payload.browser) {
          if (!surface.browser)
            surface.browser = { url: "", profileId: "default", isLoading: false };
          const b = action.payload.browser;
          if (b.url !== void 0) surface.browser.url = b.url;
          if (b.isLoading !== void 0) surface.browser.isLoading = b.isLoading;
        }
        break;
      }
      case "settings.update": {
        Object.assign(draft.settings, action.payload);
        break;
      }
    }
  }
}
const migrations = [
  // Example: { fromVersion: 1, toVersion: 2, migrate: (state) => { ... return state; } }
];
function migrateState(persisted2, filePath) {
  let { version: version2, state } = persisted2;
  if (version2 === SCHEMA_VERSION) {
    return persisted2;
  }
  if (filePath && fs.existsSync(filePath)) {
    const backupPath = filePath + SESSION_BACKUP_SUFFIX;
    try {
      fs.copyFileSync(filePath, backupPath);
    } catch (err) {
      console.error("[migrateState] Failed to create backup:", err);
    }
  }
  while (version2 < SCHEMA_VERSION) {
    const migration = migrations.find((m) => m.fromVersion === version2);
    if (!migration) {
      console.warn(
        `[migrateState] No migration found from version ${version2} to ${version2 + 1}`
      );
      break;
    }
    state = migration.migrate(state);
    version2 = migration.toVersion;
  }
  return { version: version2, state };
}
function loadPersistedState(filePath) {
  const mainResult = tryLoadFile(filePath);
  if (mainResult) return mainResult;
  const backupPath = filePath + SESSION_BACKUP_SUFFIX;
  const backupResult = tryLoadFile(backupPath);
  if (backupResult) return backupResult;
  return null;
}
function tryLoadFile(filePath) {
  try {
    if (!fs.existsSync(filePath)) return null;
    const raw = fs.readFileSync(filePath, "utf-8");
    const parsed = JSON.parse(raw);
    if (typeof parsed === "object" && parsed !== null && "version" in parsed && "state" in parsed && typeof parsed.version === "number") {
      return parsed;
    }
    return null;
  } catch {
    return null;
  }
}
class ValidationMiddleware {
  beforeMutation(action, state) {
    switch (action.type) {
      case "workspace.close": {
        const exists = state.workspaces.some(
          (ws) => ws.id === action.payload.workspaceId
        );
        if (!exists) {
          return {
            abort: true,
            reason: `Workspace not found: ${action.payload.workspaceId}`
          };
        }
        break;
      }
      case "window.close": {
        const exists = state.windows.some(
          (w) => w.id === action.payload.windowId
        );
        if (!exists) {
          return {
            abort: true,
            reason: `Window not found: ${action.payload.windowId}`
          };
        }
        break;
      }
      case "surface.close": {
        const exists = state.surfaces.some(
          (s) => s.id === action.payload.surfaceId
        );
        if (!exists) {
          return {
            abort: true,
            reason: `Surface not found: ${action.payload.surfaceId}`
          };
        }
        break;
      }
    }
    return {};
  }
}
class SideEffectsMiddleware {
  constructor(callback) {
    this.callback = callback;
  }
  afterMutation(action, _prevState, nextState) {
    switch (action.type) {
      case "workspace.create": {
        const workspaces = nextState.workspaces.filter(
          (ws) => ws.windowId === action.payload.windowId
        );
        const created = workspaces[workspaces.length - 1];
        this.callback({
          type: "workspace-created",
          workspaceId: created == null ? void 0 : created.id,
          windowId: action.payload.windowId,
          name: action.payload.name ?? "New Workspace"
        });
        break;
      }
      case "surface.close": {
        this.callback({
          type: "surface-closed",
          surfaceId: action.payload.surfaceId
        });
        break;
      }
      case "workspace.close": {
        this.callback({
          type: "workspace-closed",
          workspaceId: action.payload.workspaceId
        });
        break;
      }
      case "window.create": {
        const win = nextState.windows[nextState.windows.length - 1];
        this.callback({
          type: "window-created",
          windowId: win == null ? void 0 : win.id
        });
        break;
      }
      case "window.close": {
        this.callback({
          type: "window-closed",
          windowId: action.payload.windowId
        });
        break;
      }
      case "notification.create": {
        this.callback({
          type: "notification-created",
          title: action.payload.title,
          body: action.payload.body ?? "",
          surfaceId: action.payload.surfaceId,
          workspaceId: action.payload.workspaceId
        });
        break;
      }
    }
  }
}
class PersistenceMiddleware {
  constructor(filePath, debounceMs = 500) {
    this.timer = null;
    this.pendingState = null;
    this.hasSavedBefore = false;
    this.filePath = filePath;
    this.debounceMs = debounceMs;
  }
  post(_action, _prevState, nextState) {
    this.pendingState = nextState;
    if (this.timer) {
      clearTimeout(this.timer);
    }
    this.timer = setTimeout(() => {
      this.flush();
    }, this.debounceMs);
  }
  dispose() {
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    this.flush();
  }
  flush() {
    if (!this.pendingState) return;
    const state = this.pendingState;
    this.pendingState = null;
    this.timer = null;
    try {
      if (this.hasSavedBefore && fs.existsSync(this.filePath)) {
        const backupPath = this.filePath + SESSION_BACKUP_SUFFIX;
        fs.copyFileSync(this.filePath, backupPath);
      }
      const dir = path.dirname(this.filePath);
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
      const persisted2 = {
        version: SCHEMA_VERSION,
        state
      };
      fs.writeFileSync(this.filePath, JSON.stringify(persisted2), "utf-8");
      this.hasSavedBefore = true;
    } catch (err) {
      console.error("[PersistenceMiddleware] Failed to save state:", err);
    }
  }
  static loadState(filePath) {
    try {
      if (!fs.existsSync(filePath)) return null;
      const raw = fs.readFileSync(filePath, "utf-8");
      const parsed = JSON.parse(raw);
      if (typeof parsed === "object" && parsed !== null && "version" in parsed && "state" in parsed) {
        return parsed;
      }
      return null;
    } catch {
      return null;
    }
  }
}
const sliceMap = {
  window: "windows",
  workspace: "workspaces",
  panel: "panels",
  surface: "surfaces",
  agent: "agents",
  notification: "notifications",
  focus: "focus",
  settings: "settings"
};
function getSlice(actionType) {
  const prefix = actionType.split(".")[0];
  return sliceMap[prefix] ?? null;
}
const multiSliceActions = {
  "panel.resize": ["workspaces"],
  "panel.zoom": ["panels"],
  "panel.swap": ["workspaces"],
  "panel.split": ["panels", "surfaces", "workspaces", "focus"],
  "panel.close": ["panels", "surfaces", "workspaces"],
  "workspace.create": ["workspaces", "panels", "surfaces", "windows", "focus"],
  "workspace.close": ["workspaces", "panels", "surfaces", "windows", "focus"],
  "surface.create": ["surfaces", "panels"],
  "surface.close": ["surfaces", "panels"],
  "agent.spawn": ["panels", "surfaces", "workspaces", "agents"],
  "panel.move": ["panels", "workspaces"]
};
class IpcBroadcastMiddleware {
  constructor() {
    this.windows = /* @__PURE__ */ new Map();
  }
  registerWindow(windowId, target, onClose) {
    this.windows.set(windowId, { target, onClose });
  }
  unregisterWindow(windowId) {
    const entry = this.windows.get(windowId);
    if (entry) {
      entry.onClose();
      this.windows.delete(windowId);
    }
  }
  post(action, _prevState, nextState) {
    const slices = multiSliceActions[action.type] ?? (getSlice(action.type) ? [getSlice(action.type)] : []);
    if (slices.length === 0) return;
    const destroyed = [];
    for (const [windowId, entry] of this.windows) {
      if (entry.target.isDestroyed()) {
        destroyed.push(windowId);
        continue;
      }
      for (const sliceKey of slices) {
        entry.target.webContents.send(IPC_CHANNELS.STATE_UPDATE, sliceKey, nextState[sliceKey]);
      }
    }
    for (const id of destroyed) {
      const entry = this.windows.get(id);
      if (entry) {
        entry.onClose();
        this.windows.delete(id);
      }
    }
  }
}
class AuditLogMiddleware {
  constructor(filePath) {
    this.filePath = filePath;
  }
  post(action, _prevState, _nextState) {
    try {
      const dir = path.dirname(this.filePath);
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
      const entry = {
        timestamp: (/* @__PURE__ */ new Date()).toISOString(),
        type: action.type,
        payload: action.payload
      };
      fs.appendFileSync(
        this.filePath,
        JSON.stringify(entry) + "\n",
        "utf-8"
      );
    } catch (err) {
      console.error("[AuditLogMiddleware] Failed to write audit log:", err);
    }
  }
}
function registerIpcHandlers(store2) {
  electron.ipcMain.handle(IPC_CHANNELS.DISPATCH, (_event, rawAction) => {
    return store2.dispatch(rawAction);
  });
  electron.ipcMain.handle(
    IPC_CHANNELS.QUERY_STATE,
    (_event, query) => {
      const state = store2.getState();
      return state[query.slice];
    }
  );
  electron.ipcMain.handle(IPC_CHANNELS.GET_INITIAL_STATE, () => {
    return store2.getState();
  });
}
class WindowManager {
  constructor() {
    this.entries = /* @__PURE__ */ new Map();
  }
  /**
   * Register a window with an associated windowId and close callback.
   */
  register(windowId, win, onClose) {
    this.entries.set(windowId, { windowId, win, onClose });
  }
  /**
   * Get a managed window by its windowId.
   */
  get(windowId) {
    var _a3;
    return (_a3 = this.entries.get(windowId)) == null ? void 0 : _a3.win;
  }
  /**
   * Get all registered entries as an array of [windowId, ManagedWindow] tuples.
   */
  getAll() {
    return Array.from(this.entries.entries()).map(([id, entry]) => [
      id,
      entry.win
    ]);
  }
  /**
   * Find a window entry by its webContents id.
   */
  findByWebContentsId(webContentsId) {
    for (const entry of this.entries.values()) {
      if (entry.win.webContents.id === webContentsId) {
        return entry.win;
      }
    }
    return void 0;
  }
  /**
   * Unregister a window, invoking its onClose callback and removing it.
   */
  unregister(windowId) {
    const entry = this.entries.get(windowId);
    if (entry) {
      entry.onClose();
      this.entries.delete(windowId);
    }
  }
}
class JsonRpcRouter {
  constructor() {
    this.handlers = /* @__PURE__ */ new Map();
  }
  register(method, handler) {
    this.handlers.set(method, handler);
  }
  async handle(raw) {
    let request;
    try {
      request = JSON.parse(raw);
    } catch {
      return JSON.stringify(this.errorResponse(null, -32700, "Parse error"));
    }
    if (!request || typeof request !== "object" || request.jsonrpc !== "2.0" || typeof request.method !== "string") {
      return JSON.stringify(
        this.errorResponse((request == null ? void 0 : request.id) ?? null, -32600, "Invalid Request")
      );
    }
    const id = request.id ?? null;
    const handler = this.handlers.get(request.method);
    if (!handler) {
      return JSON.stringify(
        this.errorResponse(id, -32601, `Method not found: ${request.method}`)
      );
    }
    try {
      const result = await handler(request.params);
      return JSON.stringify(this.successResponse(id, result));
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      return JSON.stringify(this.errorResponse(id, -32603, `Internal error: ${message}`));
    }
  }
  getMethods() {
    return Array.from(this.handlers.keys());
  }
  successResponse(id, result) {
    return { jsonrpc: "2.0", id, result };
  }
  errorResponse(id, code, message) {
    return { jsonrpc: "2.0", id, error: { code, message } };
  }
}
class SocketAuth {
  constructor(mode = "cmux-only", password) {
    this.authenticatedSockets = /* @__PURE__ */ new WeakSet();
    this.mode = mode;
    this.token = crypto.randomUUID();
    this.password = password || "";
  }
  /** Get the shared secret token for cmux-only / automation modes. */
  getToken() {
    return this.token;
  }
  /** Get the current auth mode. */
  getMode() {
    return this.mode;
  }
  /** Change the auth mode at runtime. */
  setMode(mode) {
    this.mode = mode;
  }
  /**
   * Check if a connection is allowed.
   *
   * For token-based modes (cmux-only, automation), the first message must
   * contain `{"token":"<token>"}`. For password mode, `{"auth":"<password>"}`.
   *
   * Once authenticated, the socketId object is remembered in a WeakSet so
   * subsequent calls for the same socket do not require re-authentication.
   */
  authenticate(socketId, firstMessage) {
    if (this.mode === "off") {
      return { allowed: false, reason: "Socket API is disabled" };
    }
    if (this.mode === "allow-all") {
      return { allowed: true };
    }
    if (this.mode === "password") {
      if (this.authenticatedSockets.has(socketId)) {
        return { allowed: true };
      }
      try {
        const parsed = JSON.parse(firstMessage || "");
        if (parsed.auth === this.password) {
          this.authenticatedSockets.add(socketId);
          return { allowed: true };
        }
      } catch {
      }
      return { allowed: false, reason: "Invalid password" };
    }
    if (this.authenticatedSockets.has(socketId)) {
      return { allowed: true };
    }
    try {
      const parsed = JSON.parse(firstMessage || "");
      const params = parsed.params;
      const extractedToken = parsed.token ?? (params == null ? void 0 : params.token);
      if (extractedToken === this.token) {
        this.authenticatedSockets.add(socketId);
        return { allowed: true };
      }
    } catch {
    }
    return { allowed: false, reason: "Invalid token" };
  }
  /**
   * Check if a specific JSON-RPC method is allowed for the current auth mode.
   *
   * - off:       no methods allowed
   * - cmux-only: system.*, workspace.*, surface.*, panel.*, window.*, notification.*, agent.*
   * - automation: all methods (including browser.*)
   * - password:  all methods
   * - allow-all: all methods
   */
  isMethodAllowed(method) {
    if (this.mode === "off") {
      return false;
    }
    if (this.mode === "allow-all") {
      return true;
    }
    if (this.mode === "cmux-only") {
      return method.startsWith("system.") || method.startsWith("workspace.") || method.startsWith("surface.") || method.startsWith("panel.") || method.startsWith("window.") || method.startsWith("notification.") || method.startsWith("agent.") || method.startsWith("workflow.");
    }
    return true;
  }
}
class SocketApiServer {
  constructor(router2, authMode = "cmux-only") {
    this.server = null;
    this.boundPort = 0;
    this.router = router2;
    this.auth = new SocketAuth(authMode);
    process.env.CMUX_SOCKET_TOKEN = this.auth.getToken();
  }
  /** Get the auth token for child process injection. */
  getAuthToken() {
    return this.auth.getToken();
  }
  /**
   * Start the server, trying ports starting from `startPort`.
   * Returns the actual port bound (BUG-3 fix).
   */
  async start(startPort) {
    let lastError = null;
    for (let attempt = 0; attempt < MAX_SOCKET_PORT_RETRIES; attempt++) {
      try {
        const port = await this.listen(startPort + attempt);
        return port;
      } catch (err) {
        lastError = err instanceof Error ? err : new Error(String(err));
      }
    }
    throw lastError ?? new Error("Failed to start socket server");
  }
  /**
   * Attempt to listen on a specific port.
   * BUG-3 FIX: Returns the ACTUAL bound port from server.address().
   */
  listen(port) {
    return new Promise((resolve, reject) => {
      const server = net.createServer((socket) => {
        this.handleConnection(socket);
      });
      server.on("error", (err) => {
        reject(err);
      });
      server.listen(port, "127.0.0.1", () => {
        const addr = server.address();
        this.server = server;
        this.boundPort = addr.port;
        resolve(addr.port);
      });
    });
  }
  /**
   * Handle an individual TCP connection.
   * Protocol: newline-delimited JSON-RPC 2.0.
   * R2: First message must authenticate (unless auth mode is allow-all).
   */
  handleConnection(socket) {
    let buffer = "";
    let authenticated = false;
    const socketRef = socket;
    socket.on("data", (data) => {
      buffer += data.toString();
      if (buffer.length > 10 * 1024 * 1024) {
        console.error("[socket] Buffer exceeded 10 MB limit — disconnecting client");
        socket.destroy();
        return;
      }
      let newlineIdx = buffer.indexOf("\n");
      while (newlineIdx !== -1) {
        const line = buffer.substring(0, newlineIdx).trim();
        buffer = buffer.substring(newlineIdx + 1);
        if (line.length > 0) {
          if (!authenticated) {
            const authResult = this.auth.authenticate(socketRef, line);
            if (authResult.allowed) {
              authenticated = true;
              try {
                const parsed = JSON.parse(line);
                if (parsed.method === "auth.handshake") {
                  if (!socket.destroyed) {
                    socket.write(
                      JSON.stringify({ jsonrpc: "2.0", id: parsed.id ?? null, result: { ok: true } }) + "\n"
                    );
                  }
                  newlineIdx = buffer.indexOf("\n");
                  continue;
                }
              } catch {
              }
            } else {
              try {
                const parsed = JSON.parse(line);
                if (!socket.destroyed) {
                  socket.write(
                    JSON.stringify({
                      jsonrpc: "2.0",
                      id: parsed.id ?? null,
                      error: { code: -32600, message: authResult.reason || "Authentication required" }
                    }) + "\n"
                  );
                }
              } catch {
              }
              socket.destroy();
              return;
            }
          }
          let methodAllowed = true;
          try {
            const parsed = JSON.parse(line);
            if (parsed.method && !this.auth.isMethodAllowed(parsed.method)) {
              methodAllowed = false;
              if (!socket.destroyed) {
                socket.write(
                  JSON.stringify({
                    jsonrpc: "2.0",
                    id: parsed.id ?? null,
                    error: { code: -32600, message: `Method not allowed: ${parsed.method}` }
                  }) + "\n"
                );
              }
            }
          } catch {
            methodAllowed = false;
            if (!socket.destroyed) {
              socket.write(
                JSON.stringify({
                  jsonrpc: "2.0",
                  id: null,
                  error: { code: -32700, message: "Parse error" }
                }) + "\n"
              );
            }
          }
          if (methodAllowed) {
            this.router.handle(line).then((response) => {
              if (!socket.destroyed) {
                socket.write(response + "\n");
              }
            }).catch(() => {
            });
          }
        }
        newlineIdx = buffer.indexOf("\n");
      }
    });
    socket.on("error", () => {
    });
  }
  /**
   * Get the actual bound port.
   */
  getPort() {
    return this.boundPort;
  }
  /**
   * Stop the server.
   */
  async stop() {
    return new Promise((resolve, reject) => {
      if (!this.server) {
        resolve();
        return;
      }
      this.server.close((err) => {
        this.server = null;
        this.boundPort = 0;
        if (err) {
          reject(err);
        } else {
          resolve();
        }
      });
    });
  }
}
function registerSystemHandlers(router2, store2) {
  router2.register("system.ping", () => {
    return { pong: true, timestamp: Date.now() };
  });
  router2.register("system.identify", (params) => {
    const p = params;
    const state = store2.getState();
    const base = {
      name: "cmux-win",
      version: "0.1.0",
      platform: "win32"
    };
    if (p == null ? void 0 : p.surfaceId) {
      const surface = state.surfaces.find((s) => s.id === p.surfaceId);
      const panel = surface ? state.panels.find((pp) => pp.id === surface.panelId) : null;
      const workspace = panel ? state.workspaces.find((w) => w.id === panel.workspaceId) : null;
      return {
        ...base,
        caller: {
          surfaceId: p.surfaceId,
          panelId: panel == null ? void 0 : panel.id,
          paneIndex: panel == null ? void 0 : panel.paneIndex,
          workspaceId: workspace == null ? void 0 : workspace.id,
          workspaceName: workspace == null ? void 0 : workspace.name
        }
      };
    }
    return base;
  });
  router2.register("system.tree", () => {
    const state = store2.getState();
    return {
      workspaces: state.workspaces.map((ws) => ({
        id: ws.id,
        name: ws.name,
        panelLayout: ws.panelLayout,
        panels: state.panels.filter((p) => p.workspaceId === ws.id).map((p) => ({
          id: p.id,
          paneIndex: p.paneIndex,
          panelType: p.panelType,
          surfaces: state.surfaces.filter((s) => s.panelId === p.id).map((s) => ({
            id: s.id,
            surfaceType: s.surfaceType,
            title: s.title,
            terminal: s.terminal
          }))
        })),
        agents: state.agents.filter((a) => a.workspaceId === ws.id).map((a) => ({
          sessionId: a.sessionId,
          agentType: a.agentType,
          surfaceId: a.surfaceId,
          status: a.status,
          statusIcon: a.statusIcon
        }))
      })),
      focus: state.focus
    };
  });
  router2.register("system.capabilities", () => {
    return {
      methods: router2.getMethods()
    };
  });
}
function registerWindowHandlers(router2, store2) {
  router2.register("window.list", () => {
    return { windows: store2.getState().windows };
  });
  router2.register("window.current", () => {
    const state = store2.getState();
    const activeId = state.focus.activeWindowId;
    const window2 = activeId ? state.windows.find((w) => w.id === activeId) ?? null : null;
    return { window: window2 };
  });
  router2.register("window.create", (params) => {
    const p = params ?? {};
    const result = store2.dispatch({ type: "window.create", payload: { geometry: p.geometry } });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to create window");
    }
    const windows = store2.getState().windows;
    return { window: windows[windows.length - 1] };
  });
  router2.register("window.close", (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.windowId)) throw new Error("windowId is required");
    const result = store2.dispatch({ type: "window.close", payload: { windowId: p.windowId } });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to close window");
    }
    return { ok: true };
  });
}
function registerWorkspaceHandlers(router2, store2) {
  router2.register("workspace.list", () => {
    return { workspaces: store2.getState().workspaces };
  });
  router2.register("workspace.current", () => {
    const state = store2.getState();
    const activeId = state.focus.activeWorkspaceId;
    const workspace = activeId ? state.workspaces.find((ws) => ws.id === activeId) ?? null : null;
    return { workspace };
  });
  router2.register("workspace.create", (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.windowId)) throw new Error("windowId is required");
    const result = store2.dispatch({
      type: "workspace.create",
      payload: { windowId: p.windowId, name: p.name, cwd: p.cwd }
    });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to create workspace");
    }
    const workspaces = store2.getState().workspaces;
    return { workspace: workspaces[workspaces.length - 1] };
  });
  router2.register("workspace.select", (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.workspaceId)) throw new Error("workspaceId is required");
    const result = store2.dispatch({
      type: "workspace.select",
      payload: { workspaceId: p.workspaceId }
    });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to select workspace");
    }
    return { ok: true };
  });
  router2.register("workspace.close", (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.workspaceId)) throw new Error("workspaceId is required");
    const result = store2.dispatch({
      type: "workspace.close",
      payload: { workspaceId: p.workspaceId }
    });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to close workspace");
    }
    return { ok: true };
  });
  router2.register("workspace.set_layout", (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.workspaceId)) throw new Error("workspaceId is required");
    if (!(p == null ? void 0 : p.panelLayout)) throw new Error("panelLayout is required");
    const result = store2.dispatch({
      type: "workspace.set_layout",
      payload: { workspaceId: p.workspaceId, panelLayout: p.panelLayout }
    });
    if (!result.ok) throw new Error(result.error ?? "Failed to set layout");
    return { ok: true };
  });
  router2.register("workspace.rename", (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.workspaceId)) throw new Error("workspaceId is required");
    if (!(p == null ? void 0 : p.name)) throw new Error("name is required");
    const result = store2.dispatch({
      type: "workspace.rename",
      payload: { workspaceId: p.workspaceId, name: p.name }
    });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to rename workspace");
    }
    return { ok: true };
  });
}
function registerPanelHandlers(router2, store2) {
  router2.register("panel.list", () => {
    return { panels: store2.getState().panels };
  });
  router2.register("panel.focus", (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.panelId)) throw new Error("panelId is required");
    const result = store2.dispatch({
      type: "panel.focus",
      payload: { panelId: p.panelId }
    });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to focus panel");
    }
    return { ok: true };
  });
  router2.register("panel.split", (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.panelId)) throw new Error("panelId is required");
    if (!(p == null ? void 0 : p.direction)) throw new Error("direction is required");
    const panelsBefore = store2.getState().panels.length;
    const result = store2.dispatch({
      type: "panel.split",
      payload: {
        panelId: p.panelId,
        direction: p.direction,
        newPanelType: p.newPanelType ?? "terminal",
        url: p.url,
        // L4: pass URL for browser panels (dashboard, etc.)
        filePath: p.filePath
        // L4: pass filePath for markdown panels
      }
    });
    if (!result.ok) throw new Error(result.error ?? "Failed to split panel");
    const newPanels = store2.getState().panels.slice(panelsBefore);
    const newPanel = newPanels[0];
    return {
      ok: true,
      paneIndex: newPanel == null ? void 0 : newPanel.paneIndex,
      panelId: newPanel == null ? void 0 : newPanel.id,
      surfaceId: newPanel == null ? void 0 : newPanel.activeSurfaceId
    };
  });
  router2.register("panel.resize", (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.panelId)) throw new Error("panelId is required");
    if ((p == null ? void 0 : p.ratio) === void 0) throw new Error("ratio is required");
    const result = store2.dispatch({
      type: "panel.resize",
      payload: { panelId: p.panelId, ratio: p.ratio }
    });
    if (!result.ok) throw new Error(result.error ?? "Failed to resize panel");
    return { ok: true };
  });
  router2.register("panel.zoom", (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.panelId)) throw new Error("panelId is required");
    const result = store2.dispatch({
      type: "panel.zoom",
      payload: { panelId: p.panelId }
    });
    if (!result.ok) throw new Error(result.error ?? "Failed to zoom panel");
    return { ok: true };
  });
  router2.register("panel.close", (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.panelId)) throw new Error("panelId is required");
    const result = store2.dispatch({
      type: "panel.close",
      payload: { panelId: p.panelId }
    });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to close panel");
    }
    return { ok: true };
  });
}
const CSI_RE = /\x1B\[[0-9;?]*[a-zA-Z]/g;
const OSC_RE = /\x1B\][^\x07\x1B]*(?:\x07|\x1B\\)/g;
const DCS_RE = /\x1BP[^\x1B]*\x1B\\/g;
const CHARSET_RE = /\x1B[()][0-9A-B]/g;
const MISC_ESC_RE = /\x1B[>=<N~}{F|7-8]/g;
const C0_RE = /[\x00-\x08\x0B-\x0C\x0E-\x1F]/g;
function stripAnsiEscapes(s) {
  return s.replace(OSC_RE, "").replace(DCS_RE, "").replace(CSI_RE, "").replace(CHARSET_RE, "").replace(MISC_ESC_RE, "").replace(C0_RE, "");
}
function registerSurfaceHandlers(router2, store2) {
  router2.register("surface.list", () => {
    return { surfaces: store2.getState().surfaces };
  });
  router2.register("surface.create", (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.panelId)) throw new Error("panelId is required");
    const surfaceType = p.surfaceType ?? "terminal";
    const result = store2.dispatch({
      type: "surface.create",
      payload: { panelId: p.panelId, surfaceType }
    });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to create surface");
    }
    const surfaces = store2.getState().surfaces;
    return { surface: surfaces[surfaces.length - 1] };
  });
  router2.register("surface.close", (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.surfaceId)) throw new Error("surfaceId is required");
    const result = store2.dispatch({
      type: "surface.close",
      payload: { surfaceId: p.surfaceId }
    });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to close surface");
    }
    return { ok: true };
  });
  router2.register("surface.focus", (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.surfaceId)) throw new Error("surfaceId is required");
    const result = store2.dispatch({
      type: "surface.focus",
      payload: { surfaceId: p.surfaceId }
    });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to focus surface");
    }
    return { ok: true };
  });
  router2.register("surface.send_text", (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.surfaceId)) throw new Error("surfaceId is required");
    if (p.text === void 0 || p.text === null) throw new Error("text is required");
    const result = store2.dispatch({
      type: "surface.send_text",
      payload: { surfaceId: p.surfaceId, text: p.text }
    });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to send text");
    }
    return { ok: true };
  });
  router2.register("surface.read", (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.surfaceId)) throw new Error("surfaceId is required");
    const g = globalThis;
    const liveBuffers2 = g.__cmuxLiveBuffers;
    const scrollbackStore2 = g.__cmuxScrollbackStore;
    const liveRaw = liveBuffers2 == null ? void 0 : liveBuffers2.get(p.surfaceId);
    const content = liveRaw ? stripAnsiEscapes(liveRaw) : (scrollbackStore2 == null ? void 0 : scrollbackStore2.get(p.surfaceId)) ?? "";
    if (p.lines && p.lines > 0) {
      const allLines = content.split("\n");
      return { content: allLines.slice(-p.lines).join("\n") };
    }
    return { content };
  });
  router2.register("surface.health", (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.surfaceId)) throw new Error("surfaceId is required");
    const state = store2.getState();
    const surface = state.surfaces.find((s) => s.id === p.surfaceId);
    if (!surface) throw new Error("Surface not found");
    const g = globalThis;
    const liveBuffers2 = g.__cmuxLiveBuffers;
    const liveBuffer = liveBuffers2 == null ? void 0 : liveBuffers2.get(p.surfaceId);
    const agent = state.agents.find((a) => a.surfaceId === p.surfaceId);
    return {
      surfaceId: p.surfaceId,
      surfaceType: surface.surfaceType,
      title: surface.title,
      hasPty: !!liveBuffer,
      bufferSize: (liveBuffer == null ? void 0 : liveBuffer.length) ?? 0,
      terminal: surface.terminal,
      agent: agent ? {
        sessionId: agent.sessionId,
        agentType: agent.agentType,
        status: agent.status,
        lastActivity: agent.lastActivity
      } : null
    };
  });
}
const ALLOWED_SHELLS = /* @__PURE__ */ new Set([
  "powershell",
  "cmd",
  "wsl",
  "git-bash",
  "powershell.exe",
  "cmd.exe",
  "wsl.exe",
  "bash.exe",
  "bash"
]);
function shouldUseConpty(resolvedShell) {
  const lower = resolvedShell.toLowerCase();
  if (lower.includes("git") && lower.includes("bash")) {
    return false;
  }
  if (lower.includes("git") && lower.endsWith("bash.exe")) {
    return false;
  }
  return true;
}
function resolveShell(shell) {
  switch (shell) {
    case "powershell":
    case "powershell.exe":
      return "powershell.exe";
    case "cmd":
    case "cmd.exe":
      return "cmd.exe";
    case "wsl":
    case "wsl.exe":
      return "wsl.exe";
    case "bash":
    case "bash.exe":
      return "bash.exe";
    case "git-bash": {
      const candidates = [
        path.join(
          process.env["PROGRAMFILES"] ?? "C:\\Program Files",
          "Git",
          "bin",
          "bash.exe"
        ),
        path.join(
          process.env["PROGRAMFILES(X86)"] ?? "C:\\Program Files (x86)",
          "Git",
          "bin",
          "bash.exe"
        ),
        path.join(
          process.env["LOCALAPPDATA"] ?? "",
          "Programs",
          "Git",
          "bin",
          "bash.exe"
        )
      ];
      for (const candidate of candidates) {
        if (candidate && fs.existsSync(candidate)) {
          return candidate;
        }
      }
      return "bash.exe";
    }
    default:
      return shell;
  }
}
let nextId = 1;
class PtyBridge {
  constructor() {
    this.instances = /* @__PURE__ */ new Map();
  }
  /**
   * Spawn a new PTY process.
   */
  spawn(options = {}) {
    const shellName = options.shell ?? "powershell";
    if (!ALLOWED_SHELLS.has(shellName)) {
      throw new Error(`Shell not allowed: ${shellName}`);
    }
    const resolvedShell = resolveShell(shellName);
    const useConpty = shouldUseConpty(resolvedShell);
    const cols = options.cols ?? 80;
    const rows = options.rows ?? 24;
    const cwd = options.cwd ?? os.homedir();
    const env = {
      ...process.env,
      ...options.env
    };
    const ptyProcess = pty__namespace.spawn(resolvedShell, options.args ?? [], {
      name: "xterm-256color",
      cols,
      rows,
      cwd,
      env,
      useConpty
    });
    const id = `pty-${nextId++}`;
    const instance = {
      id,
      pid: ptyProcess.pid,
      process: ptyProcess.process,
      pty: ptyProcess
    };
    this.instances.set(id, instance);
    return { id, pid: ptyProcess.pid };
  }
  /**
   * Write data to a PTY instance.
   */
  write(id, data) {
    const instance = this.instances.get(id);
    if (!instance) {
      throw new Error(`PTY not found: ${id}`);
    }
    instance.pty.write(data);
  }
  /**
   * Resize a PTY instance.
   */
  resize(id, cols, rows) {
    const instance = this.instances.get(id);
    if (!instance) {
      throw new Error(`PTY not found: ${id}`);
    }
    instance.pty.resize(cols, rows);
  }
  /**
   * Kill a PTY instance and remove it from the map.
   */
  kill(id) {
    const instance = this.instances.get(id);
    if (!instance) {
      return;
    }
    try {
      instance.pty.kill();
    } catch (err) {
      console.warn(`[PtyBridge] kill(${id}) error (ignored):`, err.message);
    }
    this.instances.delete(id);
  }
  /**
   * Check whether a PTY instance exists.
   */
  has(id) {
    return this.instances.has(id);
  }
  /**
   * Subscribe to data output from a PTY instance.
   */
  onData(id, callback) {
    const instance = this.instances.get(id);
    if (!instance) {
      throw new Error(`PTY not found: ${id}`);
    }
    return instance.pty.onData(callback);
  }
  /**
   * Subscribe to exit events from a PTY instance.
   */
  onExit(id, callback) {
    const instance = this.instances.get(id);
    if (!instance) {
      throw new Error(`PTY not found: ${id}`);
    }
    return instance.pty.onExit(callback);
  }
  /**
   * Return the list of shell names available on this system.
   * Always includes 'powershell' and 'cmd'. Adds 'wsl' and 'git-bash' if detected.
   */
  getAvailableShells() {
    const shells = ["powershell", "cmd"];
    try {
      const wslPath = path.join(
        process.env["SYSTEMROOT"] ?? "C:\\Windows",
        "System32",
        "wsl.exe"
      );
      if (fs.existsSync(wslPath)) {
        shells.push("wsl");
      }
    } catch {
    }
    const gitBashCandidates = [
      path.join(
        process.env["PROGRAMFILES"] ?? "C:\\Program Files",
        "Git",
        "bin",
        "bash.exe"
      ),
      path.join(
        process.env["PROGRAMFILES(X86)"] ?? "C:\\Program Files (x86)",
        "Git",
        "bin",
        "bash.exe"
      ),
      path.join(
        process.env["LOCALAPPDATA"] ?? "",
        "Programs",
        "Git",
        "bin",
        "bash.exe"
      )
    ];
    for (const candidate of gitBashCandidates) {
      if (candidate && fs.existsSync(candidate)) {
        shells.push("git-bash");
        break;
      }
    }
    return shells;
  }
  /**
   * Get all active instance IDs.
   */
  getInstanceIds() {
    return Array.from(this.instances.keys());
  }
  /**
   * Kill all instances (cleanup on app quit).
   */
  killAll() {
    for (const id of this.instances.keys()) {
      this.kill(id);
    }
  }
}
function buildPtyEnv(surfaceId, workspaceId, baseEnv, paneIndex) {
  const env = { ...baseEnv };
  env.CMUX_SURFACE_ID = surfaceId;
  if (workspaceId) env.CMUX_WORKSPACE_ID = workspaceId;
  const binDir = env.CMUX_BIN_DIR || "";
  if (binDir) {
    const sep = process.platform === "win32" ? ";" : ":";
    env.PATH = binDir + sep + (env.PATH || "");
    if (process.platform === "win32") {
      const pathext = env.PATHEXT || ".COM;.EXE;.BAT;.CMD";
      const parts = pathext.split(";").filter(Boolean);
      const cmdIdx = parts.findIndex((p) => p.toUpperCase() === ".CMD");
      const exeIdx = parts.findIndex((p) => p.toUpperCase() === ".EXE");
      if (cmdIdx > exeIdx && exeIdx >= 0) {
        parts.splice(cmdIdx, 1);
        parts.splice(exeIdx, 0, ".CMD");
      }
      env.PATHEXT = parts.join(";");
    }
  }
  const socketPort = env.CMUX_SOCKET_PORT || "19840";
  env.CMUX_SOCKET_ADDR = `tcp://127.0.0.1:${socketPort}`;
  env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS = "1";
  env.CMUX_PANE_INDEX = `${paneIndex ?? 0}`;
  if (baseEnv.CMUX_SOCKET_TOKEN) {
    env.CMUX_SOCKET_TOKEN = baseEnv.CMUX_SOCKET_TOKEN;
  }
  return env;
}
function getShellIntegrationArgs(shell, integrationDir) {
  const env = {};
  const shellLower = shell.toLowerCase();
  if (shellLower === "powershell" || shellLower.includes("pwsh")) {
    const psScript = path.join(integrationDir, "powershell.ps1");
    return { args: ["-ExecutionPolicy", "Bypass", "-NoExit", "-Command", `. '${psScript}'`], env };
  }
  if (shellLower === "wsl") {
    const wslScript = path.join(integrationDir, "wsl", "cmux-wsl-integration.sh");
    env.CMUX_SHELL_INTEGRATION = "1";
    env.CMUX_SHELL_INTEGRATION_DIR = integrationDir;
    return { args: ["--rcfile", wslScript], env };
  }
  if (shellLower === "bash" || shellLower === "git-bash" || shellLower.includes("bash")) {
    const bashScript = path.join(integrationDir, "bash.sh");
    env.CMUX_SHELL_INTEGRATION = "1";
    env.CMUX_SHELL_INTEGRATION_DIR = integrationDir;
    return { args: ["--rcfile", bashScript], env };
  }
  if (shellLower === "cmd" || shellLower.includes("cmd.exe")) {
    const cmdScript = path.join(integrationDir, "cmd", "cmux-cmd-integration.cmd");
    env.CMUX_SHELL_INTEGRATION = "1";
    return { args: ["/k", cmdScript], env };
  }
  return { args: [], env };
}
const DEFAULT_APPROVE_PATTERNS = {
  claude: [
    { includes: ["Do you want to", "Yes"] },
    { includes: ["Esc to cancel", "1. Yes"] },
    { includes: ["requires approval", "Yes"] }
  ],
  gemini: [
    { includes: ["Apply this change"] }
  ],
  codex: [
    { includes: ["Press enter to confirm"] }
  ]
};
function loadApprovePatterns() {
  const configPath = path.join(os.homedir(), ".cmux-win", "auto-approve-patterns.json");
  try {
    if (fs.existsSync(configPath)) {
      const raw = fs.readFileSync(configPath, "utf-8");
      return JSON.parse(raw);
    }
  } catch (err) {
    console.error("[cmux-win] Failed to load auto-approve-patterns.json, using defaults:", err);
  }
  return DEFAULT_APPROVE_PATTERNS;
}
const approvePatterns = loadApprovePatterns();
const bridge = new PtyBridge();
const ptyEvents = new node_events.EventEmitter();
const surfacePtyMap = /* @__PURE__ */ new Map();
const MAX_LIVE_BUFFER = 1e5;
const liveBuffers = /* @__PURE__ */ new Map();
globalThis.__cmuxLiveBuffers = liveBuffers;
function filterSources(_surfaceId, data) {
  if (!data.includes("\n") && !data.includes("\r")) {
    return data;
  }
  const lines = data.split(/(\r?\n|\r)/);
  const filtered = [];
  for (const line of lines) {
    const stripped = line.replace(/\x1b\[[0-9;]*[a-zA-Z]/g, "").trim();
    if (/^\[\d+\]\s*https?:\/\//.test(stripped)) continue;
    if (/^Sources?\s*:?\s*$/i.test(stripped)) continue;
    if (/^출처\s*:?\s*$/.test(stripped)) continue;
    if (/^Source:\s*https?:\/\//.test(stripped)) continue;
    filtered.push(line);
  }
  return filtered.join("");
}
function registerPtyHandlers() {
  electron.ipcMain.handle(
    IPC_CHANNELS.PTY_SPAWN,
    (_event, surfaceId, options) => {
      const mergedEnv = buildPtyEnv(surfaceId, options == null ? void 0 : options.workspaceId, {
        ...process.env
      }, options == null ? void 0 : options.paneIndex);
      const integrationDir = path.join(
        mergedEnv.CMUX_BIN_DIR || path.join(__dirname, "../../resources"),
        "../shell-integration"
      );
      const shellName = (options == null ? void 0 : options.shell) || "powershell";
      const integration = getShellIntegrationArgs(shellName, integrationDir);
      Object.assign(mergedEnv, integration.env);
      const result = bridge.spawn({ ...options, env: mergedEnv, args: integration.args });
      surfacePtyMap.set(surfaceId, result.id);
      const ptyId = result.id;
      const g10 = globalThis;
      const autoApproveCooldowns = g10.__cmuxAutoApproveCooldowns || /* @__PURE__ */ new Map();
      g10.__cmuxAutoApproveCooldowns = autoApproveCooldowns;
      bridge.onData(ptyId, (data) => {
        let buf = (liveBuffers.get(surfaceId) ?? "") + data;
        if (buf.length > MAX_LIVE_BUFFER) {
          buf = buf.slice(buf.length - MAX_LIVE_BUFFER);
        }
        liveBuffers.set(surfaceId, buf);
        const stripped = data.replace(/\x1b\[[0-9;]*[a-zA-Z]/g, "");
        const now = Date.now();
        const lastApproval = autoApproveCooldowns.get(surfaceId) ?? 0;
        if (now - lastApproval > 1e3) {
          let needsApproval = false;
          for (const rules of Object.values(approvePatterns)) {
            for (const rule of rules) {
              if (rule.includes.every((p) => stripped.includes(p))) {
                needsApproval = true;
                break;
              }
            }
            if (needsApproval) break;
          }
          if (needsApproval) {
            autoApproveCooldowns.set(surfaceId, now);
            setTimeout(() => bridge.write(ptyId, "\r"), 500);
          }
        }
        const filtered = filterSources(surfaceId, data);
        if (filtered.length === 0) return;
        for (const win of electron.BrowserWindow.getAllWindows()) {
          if (!win.isDestroyed()) {
            win.webContents.send(IPC_CHANNELS.PTY_DATA, surfaceId, filtered);
          }
        }
      });
      bridge.onExit(ptyId, (exitInfo) => {
        for (const win of electron.BrowserWindow.getAllWindows()) {
          if (!win.isDestroyed()) {
            win.webContents.send(IPC_CHANNELS.PTY_EXIT, surfaceId, exitInfo);
          }
        }
        ptyEvents.emit("pty-exit", surfaceId, exitInfo);
        surfacePtyMap.delete(surfaceId);
        liveBuffers.delete(surfaceId);
      });
      return { id: result.id, pid: result.pid };
    }
  );
  electron.ipcMain.on(IPC_CHANNELS.PTY_WRITE, (_event, surfaceId, data) => {
    const ptyId = surfacePtyMap.get(surfaceId);
    if (ptyId) bridge.write(ptyId, data);
  });
  electron.ipcMain.on(IPC_CHANNELS.PTY_RESIZE, (_event, surfaceId, cols, rows) => {
    const ptyId = surfacePtyMap.get(surfaceId);
    if (ptyId) bridge.resize(ptyId, cols, rows);
  });
  electron.ipcMain.on(IPC_CHANNELS.PTY_KILL, (_event, surfaceId) => {
    const ptyId = surfacePtyMap.get(surfaceId);
    if (ptyId) {
      bridge.kill(ptyId);
      surfacePtyMap.delete(surfaceId);
      liveBuffers.delete(surfaceId);
    }
  });
  electron.ipcMain.handle(IPC_CHANNELS.PTY_HAS, (_event, surfaceId) => {
    const ptyId = surfacePtyMap.get(surfaceId);
    return ptyId ? bridge.has(ptyId) : false;
  });
  electron.ipcMain.handle(IPC_CHANNELS.PTY_GET_SHELLS, () => {
    return bridge.getAvailableShells();
  });
}
function writeToPty(surfaceId, data) {
  const ptyId = surfacePtyMap.get(surfaceId);
  if (ptyId) bridge.write(ptyId, data);
}
function killAllPty() {
  bridge.killAll();
  surfacePtyMap.clear();
}
function registerAgentHandlers(router2, store2) {
  router2.register("agent.spawn", (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.agentType)) throw new Error("agentType is required");
    if (!(p == null ? void 0 : p.workspaceId)) throw new Error("workspaceId is required");
    const panelsBefore = store2.getState().panels.length;
    const result = store2.dispatch({
      type: "agent.spawn",
      payload: {
        agentType: p.agentType,
        workspaceId: p.workspaceId,
        task: p.task
      }
    });
    if (!result.ok) throw new Error(result.error ?? "Failed to spawn agent");
    const newPanels = store2.getState().panels.slice(panelsBefore);
    const newPanel = newPanels[0];
    return {
      ok: true,
      paneIndex: newPanel == null ? void 0 : newPanel.paneIndex,
      panelId: newPanel == null ? void 0 : newPanel.id,
      surfaceId: newPanel == null ? void 0 : newPanel.activeSurfaceId
    };
  });
  router2.register("agent.session_start", (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.sessionId)) throw new Error("sessionId is required");
    if (!(p == null ? void 0 : p.agentType)) throw new Error("agentType is required");
    if (!(p == null ? void 0 : p.workspaceId)) throw new Error("workspaceId is required");
    if (!(p == null ? void 0 : p.surfaceId)) throw new Error("surfaceId is required");
    const result = store2.dispatch({
      type: "agent.session_start",
      payload: {
        sessionId: p.sessionId,
        agentType: p.agentType,
        workspaceId: p.workspaceId,
        surfaceId: p.surfaceId,
        pid: p.pid
      }
    });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to start agent session");
    }
    return { ok: true };
  });
  router2.register("agent.status_update", (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.sessionId)) throw new Error("sessionId is required");
    if (!(p == null ? void 0 : p.status)) throw new Error("status is required");
    const result = store2.dispatch({
      type: "agent.status_update",
      payload: {
        sessionId: p.sessionId,
        status: p.status,
        icon: p.icon,
        color: p.color
      }
    });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to update agent status");
    }
    return { ok: true };
  });
  router2.register("agent.session_end", (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.sessionId)) throw new Error("sessionId is required");
    const result = store2.dispatch({
      type: "agent.session_end",
      payload: { sessionId: p.sessionId }
    });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to end agent session");
    }
    return { ok: true };
  });
  const SEND_LOCK_TTL = 3e4;
  const sendLocks = /* @__PURE__ */ new Map();
  router2.register("agent.send_task", async (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.surfaceId)) throw new Error("surfaceId is required");
    if (!(p == null ? void 0 : p.task)) throw new Error("task is required");
    const lockTime = sendLocks.get(p.surfaceId);
    if (lockTime && Date.now() - lockTime < SEND_LOCK_TTL) {
      throw new Error("Another send is in progress for this surface");
    }
    sendLocks.set(p.surfaceId, Date.now());
    try {
      const g = globalThis;
      const liveBuffers2 = g.__cmuxLiveBuffers;
      if (!(liveBuffers2 == null ? void 0 : liveBuffers2.has(p.surfaceId))) {
        throw new Error("Surface has no active PTY");
      }
      const cooldowns = g.__cmuxAutoApproveCooldowns;
      cooldowns == null ? void 0 : cooldowns.set(p.surfaceId, Date.now());
      store2.dispatch({
        type: "surface.send_text",
        payload: { surfaceId: p.surfaceId, text: p.task }
      });
      await new Promise((r) => setTimeout(r, 500));
      store2.dispatch({
        type: "surface.send_text",
        payload: { surfaceId: p.surfaceId, text: "\r" }
      });
      const agent = store2.getState().agents.find((a) => a.surfaceId === p.surfaceId);
      if (agent) {
        store2.dispatch({
          type: "agent.status_update",
          payload: { sessionId: agent.sessionId, status: "running", icon: "⚡", color: "#4C8DFF" }
        });
      }
      return { ok: true, surfaceId: p.surfaceId };
    } finally {
      sendLocks.delete(p.surfaceId);
    }
  });
  router2.register("agent.rerun", async (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.surfaceId)) throw new Error("surfaceId is required");
    if (!(p == null ? void 0 : p.task)) throw new Error("task is required");
    const state = store2.getState();
    const surface = state.surfaces.find((s) => s.id === p.surfaceId);
    if (!surface) throw new Error("Surface not found");
    const agent = state.agents.find((a) => a.surfaceId === p.surfaceId);
    const agentType = p.agentType || (agent == null ? void 0 : agent.agentType) || "gemini";
    const g = globalThis;
    const liveBuffers2 = g.__cmuxLiveBuffers;
    const ptyAlive = (liveBuffers2 == null ? void 0 : liveBuffers2.has(p.surfaceId)) ?? false;
    if (agent && agent.status !== "done" && agent.status !== "error" && ptyAlive) {
      store2.dispatch({
        type: "surface.send_text",
        payload: { surfaceId: p.surfaceId, text: p.task }
      });
      await new Promise((r) => setTimeout(r, 500));
      store2.dispatch({
        type: "surface.send_text",
        payload: { surfaceId: p.surfaceId, text: "\r" }
      });
      store2.dispatch({
        type: "agent.status_update",
        payload: { sessionId: agent.sessionId, status: "running", icon: "⚡", color: "#4C8DFF" }
      });
      return { ok: true, surfaceId: p.surfaceId, mode: "interactive" };
    }
    let cmd;
    if (agentType === "gemini") {
      cmd = `gemini -i "${p.task.replace(/"/g, '\\"')}" -y`;
    } else if (agentType === "codex") {
      cmd = `codex --full-auto --no-alt-screen "${p.task.replace(/"/g, '\\"')}"`;
    } else {
      cmd = `${agentType} "${p.task.replace(/"/g, '\\"')}"`;
    }
    store2.dispatch({
      type: "surface.send_text",
      payload: { surfaceId: p.surfaceId, text: cmd + "\r" }
    });
    if (agent) {
      store2.dispatch({
        type: "agent.status_update",
        payload: { sessionId: agent.sessionId, status: "running", icon: "⚡", color: "#4C8DFF" }
      });
    }
    return { ok: true, surfaceId: p.surfaceId, mode: "relaunch" };
  });
  router2.register("agent.wait", (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.surfaceId)) throw new Error("surfaceId is required");
    const timeoutMs = p.timeout ?? 3e5;
    const startTime = Date.now();
    return new Promise((resolve) => {
      const onExit = (sid, exitInfo) => {
        if (sid === p.surfaceId) {
          clearTimeout(timer);
          ptyEvents.removeListener("pty-exit", onExit);
          resolve({ exitCode: exitInfo.exitCode, elapsed: Date.now() - startTime, timeout: false });
        }
      };
      const timer = setTimeout(() => {
        ptyEvents.removeListener("pty-exit", onExit);
        resolve({ exitCode: null, elapsed: timeoutMs, timeout: true });
      }, timeoutMs);
      ptyEvents.on("pty-exit", onExit);
      const agent = store2.getState().agents.find((a) => a.surfaceId === p.surfaceId);
      if (agent && (agent.status === "done" || agent.status === "error")) {
        clearTimeout(timer);
        ptyEvents.removeListener("pty-exit", onExit);
        resolve({ exitCode: agent.status === "done" ? 0 : 1, elapsed: 0, timeout: false });
      }
    });
  });
  router2.register("agent.output", (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.surfaceId)) throw new Error("surfaceId is required");
    const lines = p.lines ?? 50;
    const g = globalThis;
    const liveBuffers2 = g.__cmuxLiveBuffers;
    const scrollbackStore2 = g.__cmuxScrollbackStore;
    const liveRaw = liveBuffers2 == null ? void 0 : liveBuffers2.get(p.surfaceId);
    const ansiRe2 = /[\x1b\x9b][[()#;?]*(?:[0-9]{1,4}(?:;[0-9]{0,4})*)?[0-9A-ORZcf-nq-uy=><~]/g;
    const oscRe2 = /\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)/g;
    const raw = liveRaw ?? (scrollbackStore2 == null ? void 0 : scrollbackStore2.get(p.surfaceId)) ?? "";
    const clean = raw.replace(oscRe2, "").replace(ansiRe2, "");
    const allLines = clean.split("\n");
    return { content: allLines.slice(-lines).join("\n") };
  });
}
const TOKEN_FILENAME = "telegram-token.enc";
function getTokenPath(appDataDir) {
  return path.join(appDataDir, TOKEN_FILENAME);
}
function saveBotToken(appDataDir, token) {
  if (!electron.safeStorage.isEncryptionAvailable()) {
    console.warn("[telegram] safeStorage encryption not available — cannot save token");
    return false;
  }
  try {
    const dir = appDataDir;
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    const encrypted = electron.safeStorage.encryptString(token);
    fs.writeFileSync(getTokenPath(dir), encrypted);
    return true;
  } catch (err) {
    console.error("[telegram] Failed to save bot token:", err);
    return false;
  }
}
function loadBotToken(appDataDir) {
  const tokenPath = getTokenPath(appDataDir);
  if (!fs.existsSync(tokenPath)) return null;
  if (!electron.safeStorage.isEncryptionAvailable()) {
    console.warn("[telegram] safeStorage encryption not available — cannot load token");
    return null;
  }
  try {
    const encrypted = fs.readFileSync(tokenPath);
    return electron.safeStorage.decryptString(encrypted);
  } catch (err) {
    console.error("[telegram] Failed to load bot token:", err);
    return null;
  }
}
function deleteBotToken(appDataDir) {
  const tokenPath = getTokenPath(appDataDir);
  try {
    if (fs.existsSync(tokenPath)) fs.unlinkSync(tokenPath);
  } catch {
  }
}
function registerNotificationHandlers(router2, store2, appDataDir) {
  if (appDataDir) {
    router2.register("telegram.set_token", (params) => {
      const p = params;
      if (!(p == null ? void 0 : p.token)) throw new Error("token is required");
      const ok = saveBotToken(appDataDir, p.token);
      if (!ok) throw new Error("Failed to save token (encryption unavailable)");
      return { ok: true };
    });
    router2.register("telegram.get_token_status", () => {
      const token = loadBotToken(appDataDir);
      return { hasToken: token !== null };
    });
    router2.register("telegram.delete_token", () => {
      deleteBotToken(appDataDir);
      return { ok: true };
    });
    router2.register("telegram.test", async () => {
      const token = loadBotToken(appDataDir);
      if (!token) throw new Error("No bot token configured");
      const chatId = store2.getState().settings.telegram.chatId;
      if (!chatId) throw new Error("No chat ID configured");
      return { ok: true, message: "Token and chatId present" };
    });
  }
  router2.register("notification.create", (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.title)) throw new Error("title is required");
    const result = store2.dispatch({
      type: "notification.create",
      payload: {
        title: p.title,
        subtitle: p.subtitle,
        body: p.body,
        workspaceId: p.workspaceId,
        surfaceId: p.surfaceId
      }
    });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to create notification");
    }
    const notifications = store2.getState().notifications;
    return { notification: notifications[notifications.length - 1] };
  });
  router2.register("notification.list", () => {
    return { notifications: store2.getState().notifications };
  });
  router2.register("notification.clear", (params) => {
    const p = params ?? {};
    const result = store2.dispatch({
      type: "notification.clear",
      payload: { workspaceId: p.workspaceId }
    });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to clear notifications");
    }
    return { ok: true };
  });
}
function registerSettingsHandlers(router2, store2) {
  router2.register("settings.get", () => {
    return { settings: store2.getState().settings };
  });
  router2.register("settings.update", (params) => {
    const p = params;
    if (!p || typeof p !== "object" || Object.keys(p).length === 0) {
      throw new Error("settings object is required");
    }
    const result = store2.dispatch({
      type: "settings.update",
      payload: p
    });
    if (!result.ok) {
      throw new Error(result.error ?? "Failed to update settings");
    }
    return { settings: store2.getState().settings };
  });
}
let ipcMainModule = null;
let BrowserWindowModule = null;
try {
  const electron2 = require("electron");
  ipcMainModule = electron2.ipcMain;
  BrowserWindowModule = electron2.BrowserWindow;
} catch {
}
const pendingRequests = /* @__PURE__ */ new Map();
let resultListenerRegistered = false;
function ensureResultListener() {
  if (resultListenerRegistered || !ipcMainModule) return;
  resultListenerRegistered = true;
  ipcMainModule.on(
    "cmux:browser-execute-result",
    (_event, requestId, result, error) => {
      const pending = pendingRequests.get(requestId);
      if (!pending) return;
      clearTimeout(pending.timeout);
      pendingRequests.delete(requestId);
      if (error) {
        pending.reject(new Error(error));
      } else {
        pending.resolve(result);
      }
    }
  );
}
async function executeOnWebview(surfaceId, code, timeoutMs = 1e4) {
  if (!BrowserWindowModule) return null;
  ensureResultListener();
  const requestId = crypto$1.randomUUID();
  for (const win of BrowserWindowModule.getAllWindows()) {
    if (!win.isDestroyed()) {
      win.webContents.send("cmux:browser-execute", requestId, surfaceId, code);
    }
  }
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      pendingRequests.delete(requestId);
      reject(new Error("Browser execute timeout"));
    }, timeoutMs);
    pendingRequests.set(requestId, { resolve, reject, timeout });
  });
}
function registerBrowserHandlers(router2, _store) {
  router2.register("browser.eval", async (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.surfaceId)) throw new Error("surfaceId required");
    if (!(p == null ? void 0 : p.code)) throw new Error("code required");
    const result = await executeOnWebview(p.surfaceId, p.code);
    return { ok: true, result };
  });
  router2.register("browser.snapshot", async (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.surfaceId)) throw new Error("surfaceId required");
    const snapshot = await executeOnWebview(p.surfaceId, "document.documentElement.outerHTML");
    return { ok: true, snapshot };
  });
  router2.register("browser.screenshot", async (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.surfaceId)) throw new Error("surfaceId required");
    const html = await executeOnWebview(p.surfaceId, "document.documentElement.outerHTML");
    return {
      ok: true,
      format: "html",
      data: typeof html === "string" ? html : "",
      note: "Image capture requires webview.capturePage IPC (future)"
    };
  });
  router2.register("browser.click", async (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.surfaceId)) throw new Error("surfaceId required");
    if (!(p == null ? void 0 : p.ref)) throw new Error("ref required");
    await executeOnWebview(
      p.surfaceId,
      `document.querySelector('[data-cmux-ref="${p.ref}"]')?.click()`
    );
    return { ok: true };
  });
  router2.register("browser.type", async (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.surfaceId)) throw new Error("surfaceId required");
    if (!(p == null ? void 0 : p.text)) throw new Error("text required");
    const escapedText = JSON.stringify(p.text);
    await executeOnWebview(
      p.surfaceId,
      `(() => {
        const el = document.activeElement;
        if (el) {
          el.value = (el.value || '') + ${escapedText};
          el.dispatchEvent(new Event('input', { bubbles: true }));
        }
      })()`
    );
    return { ok: true };
  });
  router2.register("browser.fill", async (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.surfaceId)) throw new Error("surfaceId required");
    if (!(p == null ? void 0 : p.ref)) throw new Error("ref required");
    await executeOnWebview(
      p.surfaceId,
      `(() => {
        const el = document.querySelector('[data-cmux-ref="${p.ref}"]');
        if (el) {
          el.value = ${JSON.stringify(p.value || "")};
          el.dispatchEvent(new Event('input', { bubbles: true }));
        }
      })()`
    );
    return { ok: true };
  });
  router2.register("browser.press", async (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.surfaceId)) throw new Error("surfaceId required");
    if (!(p == null ? void 0 : p.key)) throw new Error("key required");
    await executeOnWebview(
      p.surfaceId,
      `(() => {
        const el = document.activeElement;
        if (el) {
          el.dispatchEvent(new KeyboardEvent('keydown', { key: ${JSON.stringify(p.key)}, bubbles: true }));
          el.dispatchEvent(new KeyboardEvent('keyup', { key: ${JSON.stringify(p.key)}, bubbles: true }));
        }
      })()`
    );
    return { ok: true };
  });
  router2.register("browser.wait", async (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.surfaceId)) throw new Error("surfaceId required");
    if (p.selector) {
      const timeoutMs = p.timeout || 5e3;
      await executeOnWebview(
        p.surfaceId,
        `new Promise((resolve, reject) => {
          const el = document.querySelector(${JSON.stringify(p.selector)});
          if (el) { resolve(true); return; }
          const observer = new MutationObserver(() => {
            if (document.querySelector(${JSON.stringify(p.selector)})) {
              observer.disconnect();
              resolve(true);
            }
          });
          observer.observe(document.body, { childList: true, subtree: true });
          setTimeout(() => { observer.disconnect(); reject('Timeout waiting for ' + ${JSON.stringify(p.selector)}); }, ${timeoutMs});
        })`,
        timeoutMs + 2e3
        // IPC timeout slightly longer than JS timeout
      );
    }
    return { ok: true };
  });
  router2.register("browser.navigate", async (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.surfaceId)) throw new Error("surfaceId required");
    if (!(p == null ? void 0 : p.url)) throw new Error("url required");
    await executeOnWebview(p.surfaceId, `window.location.href = ${JSON.stringify(p.url)}`);
    return { ok: true };
  });
  router2.register("browser.url.get", async (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.surfaceId)) throw new Error("surfaceId required");
    const url = await executeOnWebview(p.surfaceId, "window.location.href");
    return { url };
  });
  router2.register("browser.title.get", async (params) => {
    const p = params;
    if (!(p == null ? void 0 : p.surfaceId)) throw new Error("surfaceId required");
    const title = await executeOnWebview(p.surfaceId, "document.title");
    return { title };
  });
}
const ansiRe = /[\x1b\x9b][[()#;?]*(?:[0-9]{1,4}(?:;[0-9]{0,4})*)?[0-9A-ORZcf-nq-uy=><~]/g;
const oscRe = /\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)/g;
function readOutput(surfaceId, lines) {
  const g = globalThis;
  const liveBuffers2 = g.__cmuxLiveBuffers;
  const scrollbackStore2 = g.__cmuxScrollbackStore;
  const raw = (liveBuffers2 == null ? void 0 : liveBuffers2.get(surfaceId)) ?? (scrollbackStore2 == null ? void 0 : scrollbackStore2.get(surfaceId)) ?? "";
  const clean = raw.replace(oscRe, "").replace(ansiRe, "");
  return clean.split("\n").slice(-30).join("\n");
}
function waitForIdle(surfaceId, agentType, timeoutMs) {
  return new Promise((resolve) => {
    const g = globalThis;
    const liveBuffers2 = g.__cmuxLiveBuffers;
    const startLen = ((liveBuffers2 == null ? void 0 : liveBuffers2.get(surfaceId)) ?? "").length;
    let lastLen = startLen;
    let stableCount = 0;
    const onExit = (sid) => {
      if (sid !== surfaceId) return;
      cleanup();
      resolve({
        idle: false,
        timeout: false,
        exited: true,
        output: readOutput(surfaceId)
      });
    };
    ptyEvents.on("pty-exit", onExit);
    const idlePatterns = {
      gemini: ["Type your message", "Enter your prompt", "What can I help"],
      codex: ["What would you like", "Enter a prompt"]
    };
    const patterns = idlePatterns[agentType] || [];
    const interval = setInterval(() => {
      const raw = (liveBuffers2 == null ? void 0 : liveBuffers2.get(surfaceId)) ?? "";
      const tail = raw.slice(-500).replace(ansiRe, "");
      const patternMatch = patterns.some((p) => tail.includes(p)) && raw.length > startLen;
      const outputStable = raw.length === lastLen && raw.length > startLen;
      if (outputStable) stableCount++;
      else stableCount = 0;
      if (patternMatch && stableCount >= 2 || stableCount >= 10) {
        cleanup();
        resolve({
          idle: true,
          timeout: false,
          exited: false,
          output: readOutput(surfaceId)
        });
      }
      lastLen = raw.length;
    }, 500);
    const timer = setTimeout(() => {
      cleanup();
      resolve({
        idle: false,
        timeout: true,
        exited: false,
        output: readOutput(surfaceId)
      });
    }, timeoutMs);
    function cleanup() {
      clearInterval(interval);
      clearTimeout(timer);
      ptyEvents.removeListener("pty-exit", onExit);
    }
  });
}
function registerWorkflowHandlers(router2, store2) {
  router2.register("workflow.run", async (params) => {
    var _a3, _b;
    const p = params;
    if (!(p == null ? void 0 : p.steps) || !Array.isArray(p.steps) || p.steps.length === 0) {
      throw new Error("steps array is required");
    }
    const state = store2.getState();
    const workspaceId = p.workspaceId || state.focus.activeWorkspaceId || ((_a3 = state.workspaces[0]) == null ? void 0 : _a3.id);
    if (!workspaceId) throw new Error("No workspace available");
    const stepTimeout = p.timeout ?? 3e5;
    const results = [];
    for (let i = 0; i < p.steps.length; i++) {
      const step = p.steps[i];
      const panelsBefore = store2.getState().panels.length;
      const spawnResult = store2.dispatch({
        type: "agent.spawn",
        payload: {
          agentType: step.agent,
          workspaceId,
          task: step.task,
          cwd: step.cwd
        }
      });
      if (!spawnResult.ok) {
        results.push({ step: i, agent: step.agent, task: step.task, exitCode: -1, timeout: false, output: `Spawn failed: ${spawnResult.error}` });
        continue;
      }
      const newPanels = store2.getState().panels.slice(panelsBefore);
      const surfaceId = (_b = newPanels[0]) == null ? void 0 : _b.activeSurfaceId;
      if (!surfaceId) {
        results.push({ step: i, agent: step.agent, task: step.task, exitCode: -1, timeout: false, output: "No surface created" });
        continue;
      }
      const idleResult = await waitForIdle(surfaceId, step.agent, stepTimeout);
      results.push({
        step: i,
        agent: step.agent,
        task: step.task,
        exitCode: idleResult.exited ? 1 : idleResult.idle ? 0 : null,
        timeout: idleResult.timeout,
        output: idleResult.output
      });
    }
    return {
      name: p.name ?? "unnamed",
      stepsCompleted: results.filter((r) => r.exitCode === 0).length,
      stepsTotal: p.steps.length,
      results
    };
  });
}
const DEFAULT_SHORTCUTS = [
  // Workspace
  { id: "newWorkspace", label: "New Workspace", defaultKey: "Ctrl+N", category: "workspace" },
  {
    id: "closeWorkspace",
    label: "Close Workspace",
    defaultKey: "Ctrl+Shift+W",
    category: "workspace"
  },
  { id: "nextWorkspace", label: "Next Workspace", defaultKey: "Ctrl+Tab", category: "workspace" },
  {
    id: "prevWorkspace",
    label: "Prev Workspace",
    defaultKey: "Ctrl+Shift+Tab",
    category: "workspace"
  },
  {
    id: "renameWorkspace",
    label: "Rename Workspace",
    defaultKey: "Ctrl+Shift+R",
    category: "workspace"
  },
  // Panel
  { id: "splitRight", label: "Split Right", defaultKey: "Ctrl+D", category: "panel" },
  { id: "splitDown", label: "Split Down", defaultKey: "Ctrl+Shift+D", category: "panel" },
  { id: "closePanel", label: "Close Panel", defaultKey: "Ctrl+Shift+X", category: "panel" },
  { id: "toggleZoom", label: "Toggle Zoom", defaultKey: "Ctrl+Shift+Enter", category: "panel" },
  { id: "focusLeft", label: "Focus Left", defaultKey: "Ctrl+Alt+Left", category: "panel" },
  { id: "focusRight", label: "Focus Right", defaultKey: "Ctrl+Alt+Right", category: "panel" },
  { id: "focusUp", label: "Focus Up", defaultKey: "Ctrl+Alt+Up", category: "panel" },
  { id: "focusDown", label: "Focus Down", defaultKey: "Ctrl+Alt+Down", category: "panel" },
  // Surface
  { id: "newSurface", label: "New Tab", defaultKey: "Ctrl+Shift+T", category: "surface" },
  { id: "closeSurface", label: "Close Tab", defaultKey: "Ctrl+Shift+Q", category: "surface" },
  { id: "nextSurface", label: "Next Tab", defaultKey: "Ctrl+Shift+]", category: "surface" },
  { id: "prevSurface", label: "Prev Tab", defaultKey: "Ctrl+Shift+[", category: "surface" },
  // Navigation
  { id: "find", label: "Find", defaultKey: "Ctrl+F", category: "navigation" },
  // View
  { id: "toggleSidebar", label: "Toggle Sidebar", defaultKey: "Ctrl+B", category: "view" },
  { id: "toggleExplorer", label: "Toggle File Explorer", defaultKey: "Ctrl+E", category: "view" },
  { id: "newWindow", label: "New Window", defaultKey: "Ctrl+Shift+N", category: "view" },
  { id: "closeWindow", label: "Close Window", defaultKey: "Ctrl+Alt+W", category: "view" },
  { id: "commandPalette", label: "Command Palette", defaultKey: "Ctrl+Shift+P", category: "view" },
  { id: "openSettings", label: "Open Settings", defaultKey: "Ctrl+,", category: "view" },
  { id: "togglePanels", label: "Toggle Panels (Collapse/Expand)", defaultKey: "Ctrl+`", category: "view" },
  { id: "equalizeHorizontal", label: "Equal Width (Horizontal)", defaultKey: "Ctrl+Shift+=", category: "view" },
  { id: "equalizeVertical", label: "Equal Height (Vertical)", defaultKey: "Ctrl+Alt+=", category: "view" }
];
function parseKeyCombo(key) {
  const parts = key.split("+");
  return {
    ctrl: parts.includes("Ctrl"),
    shift: parts.includes("Shift"),
    alt: parts.includes("Alt"),
    key: parts[parts.length - 1]
  };
}
function matchInput(input, shortcuts) {
  for (const sc of shortcuts) {
    const combo = parseKeyCombo(sc.defaultKey);
    if (input.control === combo.ctrl && input.shift === combo.shift && input.alt === combo.alt && input.key.toLowerCase() === combo.key.toLowerCase()) {
      return sc.id;
    }
  }
  return null;
}
function attachShortcutInterceptor(win) {
  win.webContents.on("before-input-event", (event, input) => {
    if (input.type !== "keyDown") return;
    const shortcutId = matchInput(input, DEFAULT_SHORTCUTS);
    if (shortcutId) {
      event.preventDefault();
      win.webContents.send(IPC_CHANNELS.SHORTCUT, shortcutId);
    }
  });
}
function checkPidStatus(pid) {
  try {
    process.kill(pid, 0);
    return "alive";
  } catch (err) {
    const code = err.code;
    if (code === "ESRCH") return "dead";
    if (code === "EPERM") return "no_permission";
    return "dead";
  }
}
class HistoryDb {
  constructor(dbPath) {
    this.db = new Database(dbPath);
    this.db.pragma("journal_mode = WAL");
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id TEXT NOT NULL,
        url TEXT NOT NULL,
        title TEXT,
        visit_time INTEGER NOT NULL,
        favicon_url TEXT
      );
      CREATE INDEX IF NOT EXISTS idx_history_url ON history(url);
      CREATE INDEX IF NOT EXISTS idx_history_profile ON history(profile_id);
      CREATE INDEX IF NOT EXISTS idx_history_visit ON history(visit_time DESC);
    `);
  }
  add(profileId, url, title, faviconUrl) {
    this.db.prepare(
      "INSERT INTO history (profile_id, url, title, visit_time, favicon_url) VALUES (?, ?, ?, ?, ?)"
    ).run(profileId, url, title ?? null, Date.now(), faviconUrl ?? null);
  }
  query(profileId, prefix, limit = 10) {
    return this.db.prepare(
      `
      SELECT url, title, MAX(visit_time) as lastVisit, COUNT(*) as visits
      FROM history WHERE profile_id = ? AND url LIKE ? || '%'
      GROUP BY url ORDER BY visits DESC, lastVisit DESC LIMIT ?
    `
    ).all(profileId, prefix, limit);
  }
  clear(profileId) {
    if (profileId) {
      this.db.prepare("DELETE FROM history WHERE profile_id = ?").run(profileId);
    } else {
      this.db.exec("DELETE FROM history");
    }
  }
  close() {
    this.db.close();
  }
}
function createTelemetryConfig(enabled) {
  return {
    enabled,
    sentryDsn: process.env.SENTRY_DSN,
    posthogApiKey: process.env.POSTHOG_API_KEY
  };
}
function createUpdateConfig(channel, autoCheck) {
  return { channel, autoCheck };
}
function getUpdateConfig() {
  return { provider: "github", owner: "cmux-win", repo: "cmux-win" };
}
let autoUpdaterInstance = null;
async function initAutoUpdater(config2) {
  try {
    const { autoUpdater } = await import("electron-updater");
    autoUpdaterInstance = autoUpdater;
    autoUpdater.autoDownload = true;
    autoUpdater.channel = config2.channel;
    const ghConfig = getUpdateConfig();
    autoUpdater.setFeedURL({
      provider: ghConfig.provider,
      owner: ghConfig.owner,
      repo: ghConfig.repo
    });
    autoUpdater.on("update-available", (info) => {
      console.warn(`[cmux-win] Update available: ${info.version}`);
    });
    autoUpdater.on("update-downloaded", () => {
      console.warn("[cmux-win] Update downloaded. Will install on quit.");
    });
    autoUpdater.on("error", (err) => {
      console.error("[cmux-win] Auto-update error:", err.message);
    });
    if (config2.autoCheck) {
      autoUpdater.checkForUpdatesAndNotify().catch((_err) => {
        console.warn("[cmux-win] Update check skipped (dev mode or no publish config)");
      });
    }
  } catch {
    autoUpdaterInstance = null;
    console.warn("[cmux-win] Auto-updater not available");
  }
}
function showToast(title, body, onClick) {
  if (!electron.Notification.isSupported()) return;
  const notification = new electron.Notification({
    title,
    body: body || "",
    silent: false
  });
  notification.on("click", () => {
    {
      focusFirstWindow();
    }
  });
  notification.show();
}
function focusFirstWindow() {
  const wins = electron.BrowserWindow.getAllWindows();
  if (wins.length === 0) return;
  const win = wins[0];
  if (win.isMinimized()) win.restore();
  win.focus();
}
function computeUnreadCount(notifications) {
  if (!notifications || notifications.length === 0) return 0;
  const count = notifications.filter((n) => !n.isRead).length;
  return Math.max(0, count);
}
function formatTrayTitle(unreadCount, appName = "cmux-win") {
  if (unreadCount <= 0) return appName;
  return `(${unreadCount}) ${appName}`;
}
var mod = {};
var platform_node = {};
var browser = { exports: {} };
var ms;
var hasRequiredMs;
function requireMs() {
  if (hasRequiredMs) return ms;
  hasRequiredMs = 1;
  var s = 1e3;
  var m = s * 60;
  var h = m * 60;
  var d = h * 24;
  var w = d * 7;
  var y = d * 365.25;
  ms = function(val, options) {
    options = options || {};
    var type = typeof val;
    if (type === "string" && val.length > 0) {
      return parse2(val);
    } else if (type === "number" && isFinite(val)) {
      return options.long ? fmtLong(val) : fmtShort(val);
    }
    throw new Error(
      "val is not a non-empty string or a valid number. val=" + JSON.stringify(val)
    );
  };
  function parse2(str) {
    str = String(str);
    if (str.length > 100) {
      return;
    }
    var match = /^(-?(?:\d+)?\.?\d+) *(milliseconds?|msecs?|ms|seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h|days?|d|weeks?|w|years?|yrs?|y)?$/i.exec(
      str
    );
    if (!match) {
      return;
    }
    var n = parseFloat(match[1]);
    var type = (match[2] || "ms").toLowerCase();
    switch (type) {
      case "years":
      case "year":
      case "yrs":
      case "yr":
      case "y":
        return n * y;
      case "weeks":
      case "week":
      case "w":
        return n * w;
      case "days":
      case "day":
      case "d":
        return n * d;
      case "hours":
      case "hour":
      case "hrs":
      case "hr":
      case "h":
        return n * h;
      case "minutes":
      case "minute":
      case "mins":
      case "min":
      case "m":
        return n * m;
      case "seconds":
      case "second":
      case "secs":
      case "sec":
      case "s":
        return n * s;
      case "milliseconds":
      case "millisecond":
      case "msecs":
      case "msec":
      case "ms":
        return n;
      default:
        return void 0;
    }
  }
  function fmtShort(ms2) {
    var msAbs = Math.abs(ms2);
    if (msAbs >= d) {
      return Math.round(ms2 / d) + "d";
    }
    if (msAbs >= h) {
      return Math.round(ms2 / h) + "h";
    }
    if (msAbs >= m) {
      return Math.round(ms2 / m) + "m";
    }
    if (msAbs >= s) {
      return Math.round(ms2 / s) + "s";
    }
    return ms2 + "ms";
  }
  function fmtLong(ms2) {
    var msAbs = Math.abs(ms2);
    if (msAbs >= d) {
      return plural(ms2, msAbs, d, "day");
    }
    if (msAbs >= h) {
      return plural(ms2, msAbs, h, "hour");
    }
    if (msAbs >= m) {
      return plural(ms2, msAbs, m, "minute");
    }
    if (msAbs >= s) {
      return plural(ms2, msAbs, s, "second");
    }
    return ms2 + " ms";
  }
  function plural(ms2, msAbs, n, name) {
    var isPlural = msAbs >= n * 1.5;
    return Math.round(ms2 / n) + " " + name + (isPlural ? "s" : "");
  }
  return ms;
}
var common;
var hasRequiredCommon;
function requireCommon() {
  if (hasRequiredCommon) return common;
  hasRequiredCommon = 1;
  function setup(env) {
    createDebug.debug = createDebug;
    createDebug.default = createDebug;
    createDebug.coerce = coerce;
    createDebug.disable = disable;
    createDebug.enable = enable;
    createDebug.enabled = enabled;
    createDebug.humanize = requireMs();
    createDebug.destroy = destroy;
    Object.keys(env).forEach((key) => {
      createDebug[key] = env[key];
    });
    createDebug.names = [];
    createDebug.skips = [];
    createDebug.formatters = {};
    function selectColor(namespace) {
      let hash = 0;
      for (let i = 0; i < namespace.length; i++) {
        hash = (hash << 5) - hash + namespace.charCodeAt(i);
        hash |= 0;
      }
      return createDebug.colors[Math.abs(hash) % createDebug.colors.length];
    }
    createDebug.selectColor = selectColor;
    function createDebug(namespace) {
      let prevTime;
      let enableOverride = null;
      let namespacesCache;
      let enabledCache;
      function debug(...args) {
        if (!debug.enabled) {
          return;
        }
        const self = debug;
        const curr = Number(/* @__PURE__ */ new Date());
        const ms2 = curr - (prevTime || curr);
        self.diff = ms2;
        self.prev = prevTime;
        self.curr = curr;
        prevTime = curr;
        args[0] = createDebug.coerce(args[0]);
        if (typeof args[0] !== "string") {
          args.unshift("%O");
        }
        let index = 0;
        args[0] = args[0].replace(/%([a-zA-Z%])/g, (match, format) => {
          if (match === "%%") {
            return "%";
          }
          index++;
          const formatter = createDebug.formatters[format];
          if (typeof formatter === "function") {
            const val = args[index];
            match = formatter.call(self, val);
            args.splice(index, 1);
            index--;
          }
          return match;
        });
        createDebug.formatArgs.call(self, args);
        const logFn = self.log || createDebug.log;
        logFn.apply(self, args);
      }
      debug.namespace = namespace;
      debug.useColors = createDebug.useColors();
      debug.color = createDebug.selectColor(namespace);
      debug.extend = extend2;
      debug.destroy = createDebug.destroy;
      Object.defineProperty(debug, "enabled", {
        enumerable: true,
        configurable: false,
        get: () => {
          if (enableOverride !== null) {
            return enableOverride;
          }
          if (namespacesCache !== createDebug.namespaces) {
            namespacesCache = createDebug.namespaces;
            enabledCache = createDebug.enabled(namespace);
          }
          return enabledCache;
        },
        set: (v) => {
          enableOverride = v;
        }
      });
      if (typeof createDebug.init === "function") {
        createDebug.init(debug);
      }
      return debug;
    }
    function extend2(namespace, delimiter) {
      const newDebug = createDebug(this.namespace + (typeof delimiter === "undefined" ? ":" : delimiter) + namespace);
      newDebug.log = this.log;
      return newDebug;
    }
    function enable(namespaces) {
      createDebug.save(namespaces);
      createDebug.namespaces = namespaces;
      createDebug.names = [];
      createDebug.skips = [];
      const split = (typeof namespaces === "string" ? namespaces : "").trim().replace(/\s+/g, ",").split(",").filter(Boolean);
      for (const ns of split) {
        if (ns[0] === "-") {
          createDebug.skips.push(ns.slice(1));
        } else {
          createDebug.names.push(ns);
        }
      }
    }
    function matchesTemplate(search, template) {
      let searchIndex = 0;
      let templateIndex = 0;
      let starIndex = -1;
      let matchIndex = 0;
      while (searchIndex < search.length) {
        if (templateIndex < template.length && (template[templateIndex] === search[searchIndex] || template[templateIndex] === "*")) {
          if (template[templateIndex] === "*") {
            starIndex = templateIndex;
            matchIndex = searchIndex;
            templateIndex++;
          } else {
            searchIndex++;
            templateIndex++;
          }
        } else if (starIndex !== -1) {
          templateIndex = starIndex + 1;
          matchIndex++;
          searchIndex = matchIndex;
        } else {
          return false;
        }
      }
      while (templateIndex < template.length && template[templateIndex] === "*") {
        templateIndex++;
      }
      return templateIndex === template.length;
    }
    function disable() {
      const namespaces = [
        ...createDebug.names,
        ...createDebug.skips.map((namespace) => "-" + namespace)
      ].join(",");
      createDebug.enable("");
      return namespaces;
    }
    function enabled(name) {
      for (const skip of createDebug.skips) {
        if (matchesTemplate(name, skip)) {
          return false;
        }
      }
      for (const ns of createDebug.names) {
        if (matchesTemplate(name, ns)) {
          return true;
        }
      }
      return false;
    }
    function coerce(val) {
      if (val instanceof Error) {
        return val.stack || val.message;
      }
      return val;
    }
    function destroy() {
      console.warn("Instance method `debug.destroy()` is deprecated and no longer does anything. It will be removed in the next major version of `debug`.");
    }
    createDebug.enable(createDebug.load());
    return createDebug;
  }
  common = setup;
  return common;
}
var hasRequiredBrowser;
function requireBrowser() {
  if (hasRequiredBrowser) return browser.exports;
  hasRequiredBrowser = 1;
  (function(module2, exports$1) {
    exports$1.formatArgs = formatArgs;
    exports$1.save = save;
    exports$1.load = load;
    exports$1.useColors = useColors;
    exports$1.storage = localstorage();
    exports$1.destroy = /* @__PURE__ */ (() => {
      let warned = false;
      return () => {
        if (!warned) {
          warned = true;
          console.warn("Instance method `debug.destroy()` is deprecated and no longer does anything. It will be removed in the next major version of `debug`.");
        }
      };
    })();
    exports$1.colors = [
      "#0000CC",
      "#0000FF",
      "#0033CC",
      "#0033FF",
      "#0066CC",
      "#0066FF",
      "#0099CC",
      "#0099FF",
      "#00CC00",
      "#00CC33",
      "#00CC66",
      "#00CC99",
      "#00CCCC",
      "#00CCFF",
      "#3300CC",
      "#3300FF",
      "#3333CC",
      "#3333FF",
      "#3366CC",
      "#3366FF",
      "#3399CC",
      "#3399FF",
      "#33CC00",
      "#33CC33",
      "#33CC66",
      "#33CC99",
      "#33CCCC",
      "#33CCFF",
      "#6600CC",
      "#6600FF",
      "#6633CC",
      "#6633FF",
      "#66CC00",
      "#66CC33",
      "#9900CC",
      "#9900FF",
      "#9933CC",
      "#9933FF",
      "#99CC00",
      "#99CC33",
      "#CC0000",
      "#CC0033",
      "#CC0066",
      "#CC0099",
      "#CC00CC",
      "#CC00FF",
      "#CC3300",
      "#CC3333",
      "#CC3366",
      "#CC3399",
      "#CC33CC",
      "#CC33FF",
      "#CC6600",
      "#CC6633",
      "#CC9900",
      "#CC9933",
      "#CCCC00",
      "#CCCC33",
      "#FF0000",
      "#FF0033",
      "#FF0066",
      "#FF0099",
      "#FF00CC",
      "#FF00FF",
      "#FF3300",
      "#FF3333",
      "#FF3366",
      "#FF3399",
      "#FF33CC",
      "#FF33FF",
      "#FF6600",
      "#FF6633",
      "#FF9900",
      "#FF9933",
      "#FFCC00",
      "#FFCC33"
    ];
    function useColors() {
      if (typeof window !== "undefined" && window.process && (window.process.type === "renderer" || window.process.__nwjs)) {
        return true;
      }
      if (typeof navigator !== "undefined" && navigator.userAgent && navigator.userAgent.toLowerCase().match(/(edge|trident)\/(\d+)/)) {
        return false;
      }
      let m;
      return typeof document !== "undefined" && document.documentElement && document.documentElement.style && document.documentElement.style.WebkitAppearance || // Is firebug? http://stackoverflow.com/a/398120/376773
      typeof window !== "undefined" && window.console && (window.console.firebug || window.console.exception && window.console.table) || // Is firefox >= v31?
      // https://developer.mozilla.org/en-US/docs/Tools/Web_Console#Styling_messages
      typeof navigator !== "undefined" && navigator.userAgent && (m = navigator.userAgent.toLowerCase().match(/firefox\/(\d+)/)) && parseInt(m[1], 10) >= 31 || // Double check webkit in userAgent just in case we are in a worker
      typeof navigator !== "undefined" && navigator.userAgent && navigator.userAgent.toLowerCase().match(/applewebkit\/(\d+)/);
    }
    function formatArgs(args) {
      args[0] = (this.useColors ? "%c" : "") + this.namespace + (this.useColors ? " %c" : " ") + args[0] + (this.useColors ? "%c " : " ") + "+" + module2.exports.humanize(this.diff);
      if (!this.useColors) {
        return;
      }
      const c = "color: " + this.color;
      args.splice(1, 0, c, "color: inherit");
      let index = 0;
      let lastC = 0;
      args[0].replace(/%[a-zA-Z%]/g, (match) => {
        if (match === "%%") {
          return;
        }
        index++;
        if (match === "%c") {
          lastC = index;
        }
      });
      args.splice(lastC, 0, c);
    }
    exports$1.log = console.debug || console.log || (() => {
    });
    function save(namespaces) {
      try {
        if (namespaces) {
          exports$1.storage.setItem("debug", namespaces);
        } else {
          exports$1.storage.removeItem("debug");
        }
      } catch (error) {
      }
    }
    function load() {
      let r;
      try {
        r = exports$1.storage.getItem("debug") || exports$1.storage.getItem("DEBUG");
      } catch (error) {
      }
      if (!r && typeof process !== "undefined" && "env" in process) {
        r = process.env.DEBUG;
      }
      return r;
    }
    function localstorage() {
      try {
        return localStorage;
      } catch (error) {
      }
    }
    module2.exports = requireCommon()(exports$1);
    const { formatters } = module2.exports;
    formatters.j = function(v) {
      try {
        return JSON.stringify(v);
      } catch (error) {
        return "[UnexpectedJSONParseError]: " + error.message;
      }
    };
  })(browser, browser.exports);
  return browser.exports;
}
var hasRequiredPlatform_node;
function requirePlatform_node() {
  if (hasRequiredPlatform_node) return platform_node;
  hasRequiredPlatform_node = 1;
  (function(exports$1) {
    Object.defineProperty(exports$1, "__esModule", { value: true });
    exports$1.HttpError = exports$1.debug = void 0;
    var debug_1 = requireBrowser();
    Object.defineProperty(exports$1, "debug", { enumerable: true, get: function() {
      return debug_1.debug;
    } });
    var grammy_1 = require$$1;
    Object.defineProperty(exports$1, "HttpError", { enumerable: true, get: function() {
      return grammy_1.HttpError;
    } });
  })(platform_node);
  return platform_node;
}
var hasRequiredMod;
function requireMod() {
  if (hasRequiredMod) return mod;
  hasRequiredMod = 1;
  Object.defineProperty(mod, "__esModule", { value: true });
  mod.autoRetry = autoRetry;
  const platform_node_js_1 = requirePlatform_node();
  const debug = (0, platform_node_js_1.debug)("grammy:auto-retry");
  const ONE_HOUR = 3600;
  const INITIAL_LAST_DELAY = 3;
  function pause(seconds, signal) {
    return new Promise((resolve, reject) => {
      const handle = setTimeout(() => {
        signal === null || signal === void 0 ? void 0 : signal.removeEventListener("abort", abort);
        resolve();
      }, 1e3 * seconds);
      signal === null || signal === void 0 ? void 0 : signal.addEventListener("abort", abort);
      function abort() {
        clearTimeout(handle);
        signal === null || signal === void 0 ? void 0 : signal.removeEventListener("abort", abort);
        reject(new Error("Request aborted while waiting between retries"));
      }
    });
  }
  function autoRetry(options) {
    var _a3, _b, _c, _d;
    const maxDelay = (_a3 = options === null || options === void 0 ? void 0 : options.maxDelaySeconds) !== null && _a3 !== void 0 ? _a3 : Infinity;
    const maxRetries = (_b = options === null || options === void 0 ? void 0 : options.maxRetryAttempts) !== null && _b !== void 0 ? _b : Infinity;
    const rethrowInternalServerErrors = (_c = options === null || options === void 0 ? void 0 : options.rethrowInternalServerErrors) !== null && _c !== void 0 ? _c : false;
    const rethrowHttpErrors = (_d = options === null || options === void 0 ? void 0 : options.rethrowHttpErrors) !== null && _d !== void 0 ? _d : false;
    return async (prev, method, payload, signal) => {
      var _a4;
      let remainingAttempts = maxRetries;
      let nextDelay = INITIAL_LAST_DELAY;
      async function backoff() {
        await pause(nextDelay, signal);
        nextDelay = Math.min(ONE_HOUR, nextDelay + nextDelay);
      }
      async function call() {
        let res = void 0;
        while (res === void 0) {
          try {
            res = await prev(method, payload, signal);
          } catch (e) {
            if ((signal === void 0 || !signal.aborted) && !rethrowHttpErrors && e instanceof platform_node_js_1.HttpError) {
              debug(`HttpError thrown, will retry '${method}' after ${nextDelay} seconds (${e.message})`);
              await backoff();
              continue;
            } else {
              throw e;
            }
          }
        }
        return res;
      }
      let result = void 0;
      do {
        let retry = false;
        result = await call();
        if (typeof ((_a4 = result.parameters) === null || _a4 === void 0 ? void 0 : _a4.retry_after) === "number" && result.parameters.retry_after <= maxDelay) {
          debug(`Hit rate limit, will retry '${method}' after ${result.parameters.retry_after} seconds`);
          await pause(result.parameters.retry_after, signal);
          nextDelay = INITIAL_LAST_DELAY;
          retry = true;
        } else if (result.error_code >= 500 && !rethrowInternalServerErrors) {
          debug(`Hit internal server error, will retry '${method}' after ${nextDelay} seconds`);
          await backoff();
          retry = true;
        }
        if (!retry)
          return result;
      } while (!result.ok && remainingAttempts-- > 0);
      return result;
    };
  }
  return mod;
}
var modExports = requireMod();
const DEBOUNCE_MS = 3e3;
const CALLBACK_EXPIRY_MS = 5 * 60 * 1e3;
function escapeHtml(text) {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
class TelegramBotService {
  constructor(store2) {
    this.bot = null;
    this.chatId = "";
    this.settings = {
      enabled: false,
      chatId: "",
      forwardNotifications: true,
      remoteControl: true
    };
    this.debounceTimers = /* @__PURE__ */ new Map();
    this.networkErrorCount = 0;
    this.store = store2;
  }
  /**
   * H6: Serialized configure — await stop before start.
   * Safe to call multiple times (settings change, etc.).
   */
  async configure(settings, botToken) {
    if (this.bot) {
      const oldBot = this.bot;
      this.bot = null;
      try {
        oldBot.stop();
        await new Promise((r) => setTimeout(r, 500));
      } catch {
      }
    }
    this.settings = { ...settings };
    this.chatId = settings.chatId;
    if (!settings.enabled || !botToken || !settings.chatId) {
      return;
    }
    const bot = new require$$1.Bot(botToken);
    bot.api.config.use(modExports.autoRetry({ maxRetryAttempts: 3, maxDelaySeconds: 60 }));
    bot.catch((err) => {
      const e = err.error;
      if (e instanceof require$$1.GrammyError) {
        console.warn(`[telegram] API error ${e.error_code}: ${e.description}`);
      } else if (e instanceof require$$1.HttpError) {
        this.networkErrorCount++;
        if (this.networkErrorCount <= 3 || this.networkErrorCount % 100 === 0) {
          console.warn(`[telegram] Network error (#${this.networkErrorCount}):`, e.message);
        }
      } else {
        console.warn("[telegram] Unexpected error:", e);
      }
    });
    if (settings.remoteControl) {
      this.setupCommands(bot);
    }
    bot.on("message:text", async (ctx) => {
      if (!ctx.message.text.startsWith("/")) {
        if (String(ctx.chat.id) !== this.chatId) return;
        await ctx.reply(
          "명령어를 입력해주세요.\n\n/status — 워크스페이스 상태\n/agents — 에이전트 목록\n/approve — 대기 중인 에이전트 승인\n/reject — 대기 중인 에이전트 거부\n/send &lt;text&gt; — 텍스트 전송\n/help — 도움말",
          { parse_mode: "HTML" }
        );
      }
    });
    this.bot = bot;
    bot.start({
      drop_pending_updates: true,
      allowed_updates: ["message", "callback_query"],
      onStart: () => {
        this.networkErrorCount = 0;
        console.warn("[telegram] Bot polling started");
      }
    });
  }
  /**
   * Send notification to Telegram with InlineKeyboard.
   * H1: Must be called with .catch() — never let rejection propagate.
   * H2: Debounced per workspaceId (3 seconds).
   * H3: HTML escaped.
   */
  async sendNotification(title, body, meta) {
    if (!this.bot || !this.chatId || !this.settings.forwardNotifications) return;
    const key = (meta == null ? void 0 : meta.workspaceId) ?? "global";
    const existing = this.debounceTimers.get(key);
    if (existing) clearTimeout(existing);
    return new Promise((resolve) => {
      const timer = setTimeout(async () => {
        this.debounceTimers.delete(key);
        try {
          const safeTitle = escapeHtml(title);
          const safeBody = escapeHtml(body || "");
          let context = "";
          if (meta == null ? void 0 : meta.workspaceId) {
            const ws = this.store.getState().workspaces.find((w) => w.id === meta.workspaceId);
            if (ws) context = `

📂 <b>${escapeHtml(ws.name)}</b>`;
          }
          const now = Date.now();
          const keyboard = new require$$1.InlineKeyboard().text("✅ 승인", `approve:${(meta == null ? void 0 : meta.surfaceId) ?? ""}:${now}`).text("❌ 거부", `reject:${(meta == null ? void 0 : meta.surfaceId) ?? ""}:${now}`).row().text("📊 상태", "status");
          await this.bot.api.sendMessage(
            this.chatId,
            `🔔 <b>${safeTitle}</b>

${safeBody}${context}`,
            { parse_mode: "HTML", reply_markup: keyboard }
          );
        } catch (err) {
          console.warn("[telegram] sendNotification failed:", err.message);
        }
        resolve();
      }, DEBOUNCE_MS);
      this.debounceTimers.set(key, timer);
    });
  }
  /**
   * C3: Stop bot polling — MUST be called on app quit.
   * Synchronous for use in before-quit handler.
   */
  stop() {
    if (this.bot) {
      try {
        this.bot.stop();
      } catch {
      }
      this.bot = null;
    }
    for (const timer of this.debounceTimers.values()) clearTimeout(timer);
    this.debounceTimers.clear();
  }
  get isRunning() {
    return this.bot !== null;
  }
  // ---- Private: Inbound command handlers ----
  setupCommands(bot) {
    bot.use(async (ctx, next) => {
      var _a3;
      if (String((_a3 = ctx.chat) == null ? void 0 : _a3.id) !== this.chatId) return;
      await next();
    });
    bot.command("status", async (ctx) => {
      const state = this.store.getState();
      const lines = ["📊 <b>cmux-win 상태</b>\n"];
      for (const ws of state.workspaces) {
        const wsAgents = state.agents.filter((a) => a.workspaceId === ws.id);
        const agentInfo = wsAgents.length > 0 ? wsAgents.map((a) => `  ${a.statusIcon} ${a.agentType} (${a.status})`).join("\n") : "  (에이전트 없음)";
        lines.push(`📂 <b>${escapeHtml(ws.name)}</b>
${agentInfo}`);
      }
      if (state.workspaces.length === 0) {
        lines.push("워크스페이스가 없습니다.");
      }
      await ctx.reply(lines.join("\n"), { parse_mode: "HTML" });
    });
    bot.command("agents", async (ctx) => {
      const agents = this.store.getState().agents;
      if (agents.length === 0) {
        await ctx.reply("실행 중인 에이전트가 없습니다.");
        return;
      }
      const lines = agents.map(
        (a) => `${a.statusIcon} <b>${a.agentType}</b> — ${a.status}`
      );
      await ctx.reply(lines.join("\n"), { parse_mode: "HTML" });
    });
    bot.command("approve", async (ctx) => {
      const agent = this.findNeedsInputAgent();
      if (!agent) {
        await ctx.reply("대기 중인 에이전트가 없습니다.");
        return;
      }
      this.sendTextToSurface(agent.surfaceId, "y\r");
      await ctx.reply(`✅ ${agent.agentType} 에이전트에 승인(y) 전송 완료`);
    });
    bot.command("reject", async (ctx) => {
      const agent = this.findNeedsInputAgent();
      if (!agent) {
        await ctx.reply("대기 중인 에이전트가 없습니다.");
        return;
      }
      this.sendTextToSurface(agent.surfaceId, "n\r");
      await ctx.reply(`❌ ${agent.agentType} 에이전트에 거부(n) 전송 완료`);
    });
    bot.command("send", async (ctx) => {
      var _a3;
      const raw = (_a3 = ctx.match) == null ? void 0 : _a3.trim();
      if (!raw) {
        await ctx.reply(
          "사용법:\n/send &lt;텍스트&gt; — 활성 에이전트에 전송\n/send claude &lt;텍스트&gt; — 특정 에이전트에 전송",
          { parse_mode: "HTML" }
        );
        return;
      }
      const agentTypes = ["claude", "gemini", "codex", "opencode"];
      const firstWord = raw.split(/\s+/)[0].toLowerCase();
      let targetType = null;
      let text = raw;
      if (agentTypes.includes(firstWord)) {
        targetType = firstWord;
        text = raw.slice(firstWord.length).trim();
        if (!text) {
          await ctx.reply("전송할 텍스트를 입력하세요.");
          return;
        }
      }
      const agents = this.store.getState().agents;
      let agent = targetType ? agents.find((a) => a.agentType === targetType && a.status !== "done" && a.status !== "error") : this.findNeedsInputAgent() ?? agents.find((a) => a.status === "running");
      if (!agent) {
        await ctx.reply(targetType ? `활성 ${targetType} 에이전트가 없습니다.` : "활성 에이전트가 없습니다.");
        return;
      }
      const keyboard = new require$$1.InlineKeyboard().text("✅ 전송", `send_confirm:${agent.surfaceId}:${encodeURIComponent(text)}`).text("취소", "send_cancel");
      await ctx.reply(
        `<code>${escapeHtml(text)}</code>

위 텍스트를 <b>${escapeHtml(agent.agentType)}</b> 에이전트에 전송할까요?`,
        { parse_mode: "HTML", reply_markup: keyboard }
      );
    });
    bot.command("task", async (ctx) => {
      var _a3;
      const text = (_a3 = ctx.match) == null ? void 0 : _a3.trim();
      if (!text) {
        await ctx.reply("사용법: /task &lt;작업 내용&gt;", { parse_mode: "HTML" });
        return;
      }
      const agents = this.store.getState().agents;
      const claude = agents.find((a) => a.agentType === "claude" && a.status !== "done" && a.status !== "error");
      if (!claude) {
        const surfaces = this.store.getState().surfaces;
        if (surfaces.length === 0) {
          await ctx.reply("활성 터미널이 없습니다.");
          return;
        }
        this.sendTextToSurface(surfaces[0].id, text + "\r");
        await ctx.reply(`✅ 첫 번째 터미널에 작업 전송 완료`);
        return;
      }
      this.sendTextToSurface(claude.surfaceId, text + "\r");
      await ctx.reply(`✅ Claude 리더에게 작업 전송 완료:
<code>${escapeHtml(text)}</code>`, { parse_mode: "HTML" });
    });
    bot.command("help", async (ctx) => {
      await ctx.reply(
        "<b>cmux-win 텔레그램 봇</b>\n\n/status — 워크스페이스 + 에이전트 상태\n/agents — 에이전트 목록\n/approve — 대기 중인 에이전트 승인 (y)\n/reject — 대기 중인 에이전트 거부 (n)\n/send &lt;text&gt; — 에이전트에 텍스트 전송\n/send gemini &lt;text&gt; — 특정 에이전트에 전송\n/task &lt;text&gt; — Claude 리더에게 작업 지시\n/help — 이 도움말",
        { parse_mode: "HTML" }
      );
    });
    bot.on("callback_query:data", async (ctx) => {
      const data = ctx.callbackQuery.data;
      if (data.startsWith("approve:") || data.startsWith("reject:")) {
        const parts = data.split(":");
        const surfaceId = parts[1];
        const timestamp = parseInt(parts[2], 10);
        if (Date.now() - timestamp > CALLBACK_EXPIRY_MS) {
          await ctx.answerCallbackQuery({ text: "⏰ 만료된 버튼입니다.", show_alert: true });
          return;
        }
        const agent = surfaceId ? this.store.getState().agents.find((a) => a.surfaceId === surfaceId) : this.findNeedsInputAgent();
        if (!agent || agent.status !== "needs_input") {
          await ctx.answerCallbackQuery({
            text: "에이전트가 더 이상 입력 대기 상태가 아닙니다.",
            show_alert: true
          });
          return;
        }
        const isApprove = data.startsWith("approve:");
        this.sendTextToSurface(agent.surfaceId, isApprove ? "y\r" : "n\r");
        await ctx.answerCallbackQuery({
          text: isApprove ? "✅ 승인됨" : "❌ 거부됨"
        });
        await ctx.editMessageReplyMarkup({ reply_markup: void 0 });
        return;
      }
      if (data === "status") {
        await ctx.answerCallbackQuery();
        const state = this.store.getState();
        const lines = ["📊 <b>cmux-win 상태</b>\n"];
        for (const ws of state.workspaces) {
          const wsAgents = state.agents.filter((a) => a.workspaceId === ws.id);
          const agentInfo = wsAgents.length > 0 ? wsAgents.map((a) => `  ${a.statusIcon} ${a.agentType} (${a.status})`).join("\n") : "  (에이전트 없음)";
          lines.push(`📂 <b>${escapeHtml(ws.name)}</b>
${agentInfo}`);
        }
        await ctx.reply(lines.join("\n"), { parse_mode: "HTML" });
        return;
      }
      if (data.startsWith("send_confirm:")) {
        const parts = data.split(":");
        const surfaceId = parts[1];
        const text = decodeURIComponent(parts.slice(2).join(":"));
        this.sendTextToSurface(surfaceId, text + "\r");
        await ctx.answerCallbackQuery({ text: "✅ 전송됨" });
        await ctx.editMessageReplyMarkup({ reply_markup: void 0 });
        return;
      }
      if (data === "send_cancel") {
        await ctx.answerCallbackQuery({ text: "취소됨" });
        await ctx.editMessageReplyMarkup({ reply_markup: void 0 });
        return;
      }
      await ctx.answerCallbackQuery();
    });
  }
  findNeedsInputAgent() {
    return this.store.getState().agents.find((a) => a.status === "needs_input") ?? null;
  }
  sendTextToSurface(surfaceId, text) {
    this.store.dispatch({
      type: "surface.send_text",
      payload: { surfaceId, text }
    });
  }
}
class BridgeWatcher {
  constructor(store2) {
    this.basePath = "";
    this.heartbeatTimer = null;
    this.scanTimer = null;
    this.activePollers = /* @__PURE__ */ new Map();
    this.store = store2;
  }
  // ── Lifecycle ────────────────────────────────────────────────────────
  start() {
    const settings = this.store.getState().settings.bridge;
    this.basePath = settings.basePath || path$1.join(os$1.homedir(), "cmux-bridge");
    this.ensureDirs();
    this.scanTimer = setInterval(() => this.scanInbox(), 1e3);
    const hbMs = settings.heartbeatIntervalSec * 1e3;
    this.heartbeatTimer = setInterval(() => this.writeHeartbeat(), hbMs);
    this.writeHeartbeat();
    console.warn(`[bridge] Watching ${path$1.join(this.basePath, "inbox")}`);
  }
  stop() {
    if (this.scanTimer) {
      clearInterval(this.scanTimer);
      this.scanTimer = null;
    }
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
    for (const [, poller] of this.activePollers) {
      clearInterval(poller.timer);
    }
    this.activePollers.clear();
  }
  // ── Directory setup ──────────────────────────────────────────────────
  ensureDirs() {
    for (const dir of ["inbox", "outbox", "processed"]) {
      const p = path$1.join(this.basePath, dir);
      if (!fs$1.existsSync(p)) fs$1.mkdirSync(p, { recursive: true });
    }
  }
  // ── Inbox scanning ──────────────────────────────────────────────────
  scanInbox() {
    const inboxPath = path$1.join(this.basePath, "inbox");
    let files;
    try {
      files = fs$1.readdirSync(inboxPath).filter((f) => f.endsWith(".task.json"));
    } catch {
      return;
    }
    for (const file of files) {
      const filePath = path$1.join(inboxPath, file);
      const lockPath = filePath.replace(".task.json", `.${os$1.hostname()}.processing`);
      try {
        fs$1.renameSync(filePath, lockPath);
      } catch {
        continue;
      }
      try {
        const content = fs$1.readFileSync(lockPath, "utf8");
        const task = JSON.parse(content);
        this.processTask(task, lockPath);
      } catch (err) {
        console.error("[bridge] Failed to parse task:", err);
        this.writeResult({
          id: "parse-error",
          status: "error",
          output: `Parse error: ${err}`,
          started_at: (/* @__PURE__ */ new Date()).toISOString(),
          ended_at: (/* @__PURE__ */ new Date()).toISOString(),
          panel: -1
        });
        this.moveToProcessed(lockPath);
      }
    }
  }
  // ── Task processing ─────────────────────────────────────────────────
  processTask(task, lockPath) {
    const state = this.store.getState();
    const panel = state.panels.find((p) => p.paneIndex === task.target_panel);
    if (!panel) {
      this.writeResult({
        id: task.id,
        status: "error",
        output: `Panel %${task.target_panel} not found`,
        started_at: (/* @__PURE__ */ new Date()).toISOString(),
        ended_at: (/* @__PURE__ */ new Date()).toISOString(),
        panel: task.target_panel
      });
      this.moveToProcessed(lockPath);
      return;
    }
    const surfaceId = panel.activeSurfaceId;
    const startedAt = (/* @__PURE__ */ new Date()).toISOString();
    let prompt = task.prompt;
    if (task.mode === "leader") {
      prompt = "다음 작업을 수행해. 필요하면 tmux split-window -h로 다른 AI(gemini, codex)를 실행해서 협업해:\n" + prompt;
    }
    this.store.dispatch({
      type: "surface.send_text",
      payload: { surfaceId, text: prompt + "\r" }
    });
    console.warn(`[bridge] Task ${task.id} → panel %${task.target_panel} (${task.mode})`);
    this.startPolling(task.id, surfaceId, startedAt, task.timeout_sec, lockPath, task.target_panel);
  }
  // ── Result polling (polled-diff pattern — buffer overflow safe) ─────
  startPolling(taskId, surfaceId, startedAt, timeoutSec, lockPath, panelIndex) {
    const pollMs = this.store.getState().settings.bridge.pollIntervalSec * 1e3;
    const deadline = Date.now() + timeoutSec * 1e3;
    const liveBuffers2 = globalThis.__cmuxLiveBuffers;
    const poller = {
      timer: null,
      accumulatedOutput: "",
      lastBufferLength: ((liveBuffers2 == null ? void 0 : liveBuffers2.get(surfaceId)) ?? "").length,
      lastNewOutputTime: Date.now()
    };
    poller.timer = setInterval(() => {
      const buf = (liveBuffers2 == null ? void 0 : liveBuffers2.get(surfaceId)) ?? "";
      if (buf.length < poller.lastBufferLength) {
        poller.lastBufferLength = 0;
      }
      const newPart = buf.slice(poller.lastBufferLength);
      poller.lastBufferLength = buf.length;
      if (newPart.length > 0) {
        poller.accumulatedOutput += newPart;
        poller.lastNewOutputTime = Date.now();
      }
      const clean = poller.accumulatedOutput.replace(/\x1b\[[0-9;]*[a-zA-Z]/g, "");
      const hasMarker = clean.includes("===BRIDGE_DONE===") || clean.includes("===END===") || clean.includes("작업완료") || clean.includes("DONE");
      const isIdle = Date.now() - poller.lastNewOutputTime > 3e3;
      const isTimeout = Date.now() > deadline;
      if (hasMarker && isIdle || isTimeout) {
        clearInterval(poller.timer);
        this.activePollers.delete(taskId);
        this.writeResult({
          id: taskId,
          status: isTimeout ? "timeout" : "completed",
          output: clean,
          started_at: startedAt,
          ended_at: (/* @__PURE__ */ new Date()).toISOString(),
          panel: panelIndex
        });
        this.moveToProcessed(lockPath);
        console.warn(
          `[bridge] Task ${taskId} ${isTimeout ? "timed out" : "completed"} (${Math.round((Date.now() - new Date(startedAt).getTime()) / 1e3)}s)`
        );
      }
    }, pollMs);
    this.activePollers.set(taskId, poller);
  }
  // ── Result writing ──────────────────────────────────────────────────
  writeResult(result) {
    const outPath = path$1.join(this.basePath, "outbox", `${result.id}.result.json`);
    try {
      fs$1.writeFileSync(outPath, JSON.stringify(result, null, 2));
    } catch (err) {
      console.error("[bridge] Failed to write result:", err);
    }
  }
  moveToProcessed(lockPath) {
    const dest = path$1.join(this.basePath, "processed", path$1.basename(lockPath));
    try {
      fs$1.renameSync(lockPath, dest);
    } catch {
      try {
        fs$1.unlinkSync(lockPath);
      } catch {
      }
    }
  }
  // ── Heartbeat ───────────────────────────────────────────────────────
  writeHeartbeat() {
    const state = this.store.getState();
    const heartbeat = {
      alive: true,
      ts: (/* @__PURE__ */ new Date()).toISOString(),
      hostname: os$1.hostname(),
      panels: state.panels.map((p) => ({
        index: p.paneIndex,
        type: p.panelType,
        surface: p.activeSurfaceId
      })),
      agents: state.agents.map((a) => ({
        type: a.agentType,
        status: a.status,
        surface: a.surfaceId
      }))
    };
    try {
      fs$1.writeFileSync(path$1.join(this.basePath, "heartbeat.json"), JSON.stringify(heartbeat, null, 2));
    } catch {
    }
  }
}
process.on("uncaughtException", (err) => {
  var _a3;
  if ((_a3 = err.message) == null ? void 0 : _a3.includes("AttachConsole")) {
    console.warn("[cmux-win] ConPTY AttachConsole error (ignored):", err.message);
    return;
  }
  console.error("[cmux-win] Uncaught exception:", err);
  throw err;
});
const gotSingleInstanceLock = electron.app.requestSingleInstanceLock();
if (!gotSingleInstanceLock) {
  electron.app.quit();
}
const sessionFilePath = path.join(electron.app.getPath("appData"), "cmux-win", "session.json");
const debugLogPath = path.join(electron.app.getPath("temp"), "cmux-win-debug.log");
let initialState;
let lastWindowGeometry;
const persisted = loadPersistedState(sessionFilePath);
if (persisted) {
  const migrated = migrateState(persisted, sessionFilePath);
  lastWindowGeometry = (_a2 = migrated.state.windows[0]) == null ? void 0 : _a2.geometry;
  const mergedSettings = { ...DEFAULT_SETTINGS, ...migrated.state.settings };
  initialState = {
    ...migrated.state,
    settings: mergedSettings,
    windows: [],
    agents: [],
    workspaces: [],
    panels: [],
    surfaces: []
  };
}
const scrollbackPath = path.join(
  process.env.APPDATA || path.join(os.homedir(), "AppData", "Roaming"),
  "cmux-win",
  "scrollback.json"
);
const scrollbackStore = /* @__PURE__ */ new Map();
globalThis.__cmuxScrollbackStore = scrollbackStore;
let scrollbackSaveTimer = null;
try {
  const raw = fs.readFileSync(scrollbackPath, "utf8");
  const data = JSON.parse(raw);
  for (const [k, v] of Object.entries(data)) scrollbackStore.set(k, v);
} catch {
}
const store = new AppStateStore(initialState);
const validationMw = new ValidationMiddleware();
const sideEffectsMw = new SideEffectsMiddleware((effect) => {
  store.emit("side-effect", effect);
});
const persistenceMw = new PersistenceMiddleware(sessionFilePath, SESSION_SAVE_DEBOUNCE_MS);
const ipcBroadcastMw = new IpcBroadcastMiddleware();
const auditLogMw = new AuditLogMiddleware(debugLogPath);
store.use(validationMw);
store.use(sideEffectsMw);
store.use(persistenceMw);
store.use(ipcBroadcastMw);
store.use(auditLogMw);
registerIpcHandlers(store);
registerPtyHandlers();
electron.ipcMain.on("window:minimize", (event) => {
  var _a3;
  (_a3 = electron.BrowserWindow.fromWebContents(event.sender)) == null ? void 0 : _a3.minimize();
});
electron.ipcMain.on("window:maximize", (event) => {
  const win = electron.BrowserWindow.fromWebContents(event.sender);
  if (win == null ? void 0 : win.isMaximized()) win.unmaximize();
  else win == null ? void 0 : win.maximize();
});
electron.ipcMain.on("window:close", (event) => {
  var _a3;
  (_a3 = electron.BrowserWindow.fromWebContents(event.sender)) == null ? void 0 : _a3.close();
});
electron.ipcMain.handle("cmux:open-external", async (_event, url) => {
  const { shell } = await import("electron");
  return shell.openExternal(url);
});
electron.ipcMain.handle("cmux:open-path", async (_event, filePath) => {
  const { shell } = await import("electron");
  const cleanPath = filePath.replace(/:\d+$/, "");
  return shell.openPath(cleanPath);
});
const windowManager = new WindowManager();
let appTray = null;
const telegramBot = new TelegramBotService(store);
store.on("side-effect", (effect) => {
  if (effect.type === "pty-write" && effect.surfaceId && effect.text !== void 0) {
    writeToPty(effect.surfaceId, effect.text);
  }
  if (effect.type === "notification-created") {
    const title = effect.title || "cmux-win";
    const body = effect.body || "";
    showToast(title, body);
    if (appTray) {
      const unread = computeUnreadCount(store.getState().notifications);
      appTray.setToolTip(formatTrayTitle(unread));
    }
    telegramBot.sendNotification(title, body, {
      workspaceId: effect.workspaceId,
      surfaceId: effect.surfaceId
    }).catch((err) => console.warn("[telegram] send failed:", err.message));
  }
});
ptyEvents.on("pty-exit", (surfaceId, exitInfo) => {
  const state = store.getState();
  const agent = state.agents.find((a) => a.surfaceId === surfaceId);
  if (agent) {
    store.dispatch({
      type: "agent.status_update",
      payload: {
        sessionId: agent.sessionId,
        status: exitInfo.exitCode === 0 ? "done" : "error",
        icon: exitInfo.exitCode === 0 ? "✅" : "❌",
        color: exitInfo.exitCode === 0 ? "#4CAF50" : "#F44336"
      }
    });
  }
  store.dispatch({
    type: "surface.update_meta",
    payload: { surfaceId, terminal: { exitCode: exitInfo.exitCode } }
  });
});
const router = new JsonRpcRouter();
registerSystemHandlers(router, store);
registerWindowHandlers(router, store);
registerWorkspaceHandlers(router, store);
registerPanelHandlers(router, store);
registerSurfaceHandlers(router, store);
registerAgentHandlers(router, store);
registerNotificationHandlers(router, store, electron.app.getPath("userData"));
registerSettingsHandlers(router, store);
registerBrowserHandlers(router);
registerWorkflowHandlers(router, store);
const socketServer = new SocketApiServer(router, store.getState().settings.socket.mode);
let historyDb = null;
async function createWindow() {
  const win = new electron.BrowserWindow({
    width: (lastWindowGeometry == null ? void 0 : lastWindowGeometry.width) ?? 1200,
    height: (lastWindowGeometry == null ? void 0 : lastWindowGeometry.height) ?? 800,
    x: lastWindowGeometry == null ? void 0 : lastWindowGeometry.x,
    y: lastWindowGeometry == null ? void 0 : lastWindowGeometry.y,
    center: !lastWindowGeometry,
    show: false,
    title: "cmux-win",
    frame: false,
    backgroundColor: "#272822",
    webPreferences: {
      preload: path.join(__dirname, "../preload/index.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      webviewTag: true
    }
  });
  store.dispatch({ type: "window.create", payload: {} });
  const windowId = store.getState().windows.at(-1).id;
  windowManager.register(windowId, win, () => {
    ipcBroadcastMw.unregisterWindow(windowId);
  });
  ipcBroadcastMw.registerWindow(windowId, win, () => {
    windowManager.unregister(windowId);
  });
  attachShortcutInterceptor(win);
  return new Promise((resolve) => {
    win.webContents.on("console-message", (_event, level, message, line, sourceId) => {
      if (level >= 2) {
        console.warn(`[Renderer:${level}] ${message} (${sourceId}:${line})`);
      }
    });
    win.webContents.on("did-finish-load", () => {
      win.webContents.send(IPC_CHANNELS.WINDOW_ID, windowId);
      win.show();
      resolve(win);
    });
    const rendererUrl = process.env.ELECTRON_RENDERER_URL;
    if (rendererUrl) {
      win.loadURL(rendererUrl);
    } else {
      win.loadFile(path.join(__dirname, "../renderer/index.html"));
    }
  });
}
electron.app.whenReady().then(async () => {
  electron.app.setAppUserModelId("com.cmux-win.app");
  try {
    const historyPath = path.join(electron.app.getPath("appData"), "cmux-win", "history.db");
    historyDb = new HistoryDb(historyPath);
  } catch (err) {
    console.error("[cmux-win] Failed to init history DB:", err);
  }
  if (historyDb) {
    electron.ipcMain.handle(
      "browser:history:query",
      (_, args) => historyDb.query(args.profileId, args.prefix, args.limit)
    );
    electron.ipcMain.handle(
      "browser:history:add",
      (_, args) => historyDb.add(args.profileId, args.url, args.title, args.faviconUrl)
    );
    electron.ipcMain.handle(
      "browser:history:clear",
      (_, args) => historyDb.clear(args.profileId)
    );
  }
  electron.ipcMain.on(IPC_CHANNELS.SCROLLBACK_SAVE, (_event, surfaceId, content) => {
    scrollbackStore.set(surfaceId, content);
    if (scrollbackSaveTimer) clearTimeout(scrollbackSaveTimer);
    scrollbackSaveTimer = setTimeout(() => {
      try {
        const dir = path.dirname(scrollbackPath);
        if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
        const tmp = scrollbackPath + ".tmp";
        fs.writeFileSync(tmp, JSON.stringify(Object.fromEntries(scrollbackStore)));
        fs.renameSync(tmp, scrollbackPath);
      } catch (err) {
        console.error("[cmux-win] scrollback save error:", err);
      }
    }, 5e3);
  });
  electron.ipcMain.handle(IPC_CHANNELS.SCROLLBACK_LOAD, (_event, surfaceId) => {
    return scrollbackStore.get(surfaceId) ?? null;
  });
  electron.ipcMain.handle(IPC_CHANNELS.FILE_READ, async (_event, filePath) => {
    try {
      if (!path.isAbsolute(filePath)) {
        return { error: "Only absolute file paths are allowed" };
      }
      const content = await fs.promises.readFile(filePath, "utf8");
      return { content };
    } catch (err) {
      return { error: err instanceof Error ? err.message : "Failed to read file" };
    }
  });
  electron.ipcMain.handle(IPC_CHANNELS.FILE_LIST_DIR, async (_event, dirPath) => {
    try {
      if (!path.isAbsolute(dirPath)) {
        return { error: "Only absolute paths are allowed" };
      }
      const dirents = await fs.promises.readdir(dirPath, { withFileTypes: true });
      const entries = dirents.map((d) => ({
        name: d.name,
        isDirectory: d.isDirectory(),
        path: path.join(dirPath, d.name)
      }));
      entries.sort((a, b) => {
        if (a.isDirectory !== b.isDirectory) return a.isDirectory ? -1 : 1;
        return a.name.localeCompare(b.name);
      });
      return { entries };
    } catch (err) {
      return { error: err instanceof Error ? err.message : "Failed to list directory" };
    }
  });
  const fileWatchers = /* @__PURE__ */ new Map();
  electron.ipcMain.on(IPC_CHANNELS.FILE_WATCH, (event, filePath) => {
    if (fileWatchers.has(filePath)) return;
    try {
      const watcher = fs.watch(filePath, { persistent: false }, () => {
        event.sender.send(IPC_CHANNELS.FILE_CHANGED, filePath);
      });
      watcher.on("error", () => {
        fileWatchers.delete(filePath);
      });
      fileWatchers.set(filePath, watcher);
    } catch {
    }
  });
  electron.ipcMain.on(IPC_CHANNELS.FILE_UNWATCH, (_event, filePath) => {
    const watcher = fileWatchers.get(filePath);
    if (watcher) {
      watcher.close();
      fileWatchers.delete(filePath);
    }
  });
  electron.ipcMain.handle(IPC_CHANNELS.DIALOG_OPEN_FOLDER, async () => {
    const win2 = electron.BrowserWindow.getFocusedWindow();
    const result = await electron.dialog.showOpenDialog(win2, { properties: ["openDirectory"] });
    if (result.canceled || result.filePaths.length === 0) {
      return { cancelled: true };
    }
    return { path: result.filePaths[0] };
  });
  const telegramAppDataDir = electron.app.getPath("userData");
  const telegramSettings = store.getState().settings.telegram;
  const telegramToken = loadBotToken(telegramAppDataDir);
  void telegramBot.configure(telegramSettings, telegramToken).catch((err) => {
    console.error("[telegram] Failed to start bot:", err.message);
  });
  store.on("change", (action) => {
    if ((action == null ? void 0 : action.type) === "settings.update") {
      const newSettings = store.getState().settings.telegram;
      const token = loadBotToken(telegramAppDataDir);
      void telegramBot.configure(newSettings, token).catch((err) => {
        console.error("[telegram] Failed to reconfigure bot:", err.message);
      });
    }
  });
  const bridgeWatcher2 = new BridgeWatcher(store);
  if (store.getState().settings.bridge.enabled) {
    bridgeWatcher2.start();
  }
  store.on("change", (action) => {
    if ((action == null ? void 0 : action.type) === "settings.update") {
      const bridgeSettings = store.getState().settings.bridge;
      bridgeWatcher2.stop();
      if (bridgeSettings.enabled) {
        bridgeWatcher2.start();
      }
    }
  });
  createTelemetryConfig(store.getState().settings.telemetry.enabled);
  const updateConfig = createUpdateConfig(
    store.getState().settings.updates.channel,
    store.getState().settings.updates.autoCheck
  );
  void initAutoUpdater(updateConfig);
  try {
    const actualPort = await socketServer.start(DEFAULT_SOCKET_PORT);
    process.env.CMUX_SOCKET_PORT = String(actualPort);
    const srcBinDir = path.join(__dirname, "../../resources/bin");
    const safeBinDir = path.join(os.homedir(), ".cmux-win", "bin");
    try {
      if (!fs.existsSync(safeBinDir)) fs.mkdirSync(safeBinDir, { recursive: true });
      for (const f of ["tmux.cmd", "tmux-shim.js", "claude.cmd", "claude-wrapper.js", "claude-wrapper-lib.js", "cmux.cmd", "cmux-cli.js"]) {
        const src = path.join(srcBinDir, f);
        const dst = path.join(safeBinDir, f);
        if (fs.existsSync(src)) fs.copyFileSync(src, dst);
      }
      const srcShellDir = path.join(__dirname, "../../resources/shell-integration");
      const dstShellDir = path.join(os.homedir(), ".cmux-win", "shell-integration");
      try {
        const copyRecursive = (src, dst) => {
          const stat = fs.statSync(src);
          if (stat.isDirectory()) {
            if (!fs.existsSync(dst)) fs.mkdirSync(dst, { recursive: true });
            for (const f of fs.readdirSync(src)) copyRecursive(path.join(src, f), path.join(dst, f));
          } else {
            fs.copyFileSync(src, dst);
          }
        };
        if (fs.existsSync(srcShellDir)) copyRecursive(srcShellDir, dstShellDir);
      } catch (err) {
        console.error("[cmux-win] Failed to copy shell-integration files:", err);
      }
      const bashShimContent = '#!/usr/bin/env node\nconst path = require("path");\nrequire(path.join(__dirname, "tmux-shim.js"));\n';
      const bashShim = path.join(safeBinDir, "tmux");
      fs.writeFileSync(bashShim, bashShimContent);
      try {
        fs.chmodSync(bashShim, 493);
      } catch {
      }
      const userBinDir = path.join(os.homedir(), "bin");
      try {
        if (!fs.existsSync(userBinDir)) fs.mkdirSync(userBinDir, { recursive: true });
        fs.writeFileSync(path.join(userBinDir, "tmux"), bashShimContent);
        fs.copyFileSync(path.join(safeBinDir, "tmux-shim.js"), path.join(userBinDir, "tmux-shim.js"));
        try {
          fs.chmodSync(path.join(userBinDir, "tmux"), 493);
        } catch {
        }
      } catch (err) {
        console.error("[cmux-win] Failed to copy shims to ~/bin/:", err);
      }
    } catch (err) {
      console.error("[cmux-win] Failed to copy shim files:", err);
    }
    process.env.CMUX_BIN_DIR = safeBinDir;
    const srcCliPath = path.join(__dirname, "../cli/cmux-win.js");
    const safeCliPath = path.join(os.homedir(), ".cmux-win", "cli", "cmux-win.js");
    try {
      const cliDir = path.dirname(safeCliPath);
      if (!fs.existsSync(cliDir)) fs.mkdirSync(cliDir, { recursive: true });
      if (fs.existsSync(srcCliPath)) fs.copyFileSync(srcCliPath, safeCliPath);
    } catch {
    }
    process.env.CMUX_CLI_PATH = fs.existsSync(safeCliPath) ? safeCliPath : srcCliPath;
    console.warn(`[cmux-win] Socket API listening on port ${actualPort}`);
    console.warn(`[cmux-win] Bin dir: ${safeBinDir}`);
    const tokenPath = path.join(electron.app.getPath("userData"), "socket-token");
    fs.writeFileSync(tokenPath, `${process.env.CMUX_SOCKET_TOKEN}
${actualPort}`);
    try {
      const mcpSrc = path.join(__dirname, "../../resources/mcp/cmux-mcp-server.js");
      const mcpDst = path.join(os.homedir(), ".cmux-win", "mcp", "cmux-mcp-server.js");
      const mcpDir = path.dirname(mcpDst);
      if (!fs.existsSync(mcpDir)) fs.mkdirSync(mcpDir, { recursive: true });
      if (fs.existsSync(mcpSrc)) fs.copyFileSync(mcpSrc, mcpDst);
      const configPaths = [];
      const roaming = process.env.APPDATA || "";
      const local = process.env.LOCALAPPDATA || "";
      const stdPath = path.join(roaming, "Claude", "claude_desktop_config.json");
      if (fs.existsSync(stdPath)) configPaths.push(stdPath);
      try {
        for (const d of fs.readdirSync(path.join(local, "Packages"))) {
          if (!d.startsWith("Claude_")) continue;
          const p = path.join(local, "Packages", d, "LocalCache", "Roaming", "Claude", "claude_desktop_config.json");
          if (fs.existsSync(p)) configPaths.push(p);
        }
      } catch {
      }
      for (const cfgPath of configPaths) {
        const cfg = JSON.parse(fs.readFileSync(cfgPath, "utf8"));
        if (!cfg.mcpServers) cfg.mcpServers = {};
        const newEntry = { command: "node", args: [mcpDst.replace(/\\/g, "/")] };
        const existing = cfg.mcpServers["cmux-win"];
        if (JSON.stringify(existing) !== JSON.stringify(newEntry)) {
          cfg.mcpServers["cmux-win"] = newEntry;
          fs.writeFileSync(cfgPath, JSON.stringify(cfg, null, 2));
          console.warn(`[cmux-win] MCP server registered → ${cfgPath}`);
        } else {
          console.warn(`[cmux-win] MCP config unchanged, skip write → ${cfgPath}`);
        }
      }
    } catch (mcpErr) {
      console.warn("[cmux-win] MCP auto-register skipped:", mcpErr.message);
    }
  } catch (err) {
    console.error("[cmux-win] Failed to start socket server:", err);
  }
  setInterval(() => {
    const agents = store.getState().agents;
    for (const agent of agents) {
      if (!agent.pid) continue;
      const status = checkPidStatus(agent.pid);
      if (status === "dead") {
        store.dispatch({
          type: "agent.session_end",
          payload: { sessionId: agent.sessionId }
        });
      }
    }
  }, 1e4);
  const win = await createWindow();
  const windowId = store.getState().windows.at(-1).id;
  const iconPath = path.join(__dirname, "../../resources/icon.png");
  const trayIcon = fs.existsSync(iconPath) ? electron.nativeImage.createFromPath(iconPath) : electron.nativeImage.createEmpty();
  const tray = new electron.Tray(trayIcon);
  tray.setToolTip(formatTrayTitle(0));
  tray.setContextMenu(
    electron.Menu.buildFromTemplate([
      { label: "Show", click: () => win.show() },
      { label: "Quit", click: () => electron.app.quit() }
    ])
  );
  appTray = tray;
  store.adoptOrphanWorkspaces(windowId);
  electron.app.on("second-instance", () => {
    const wins = electron.BrowserWindow.getAllWindows();
    if (wins.length > 0) {
      if (wins[0].isMinimized()) wins[0].restore();
      wins[0].focus();
    }
  });
  electron.app.on("activate", () => {
    if (electron.BrowserWindow.getAllWindows().length === 0) {
      void createWindow();
    }
  });
});
store.on("change", (action) => {
  var _a3;
  if ((action == null ? void 0 : action.type) === "surface.close" && ((_a3 = action == null ? void 0 : action.payload) == null ? void 0 : _a3.surfaceId)) {
    scrollbackStore.delete(action.payload.surfaceId);
  }
});
electron.app.on("before-quit", () => {
  telegramBot.stop();
  bridgeWatcher.stop();
  try {
    const tokenPath = path.join(electron.app.getPath("userData"), "socket-token");
    if (fs.existsSync(tokenPath)) fs.unlinkSync(tokenPath);
  } catch {
  }
  try {
    const dir = path.dirname(scrollbackPath);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(scrollbackPath, JSON.stringify(Object.fromEntries(scrollbackStore)));
  } catch {
  }
});
electron.app.on("window-all-closed", () => {
  killAllPty();
  persistenceMw.dispose();
  historyDb == null ? void 0 : historyDb.close();
  socketServer.stop().catch((err) => {
    console.error("[cmux-win] Error stopping socket server:", err);
  });
  electron.app.quit();
});
