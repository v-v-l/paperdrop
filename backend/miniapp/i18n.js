/**
 * Minimal i18n helper for the Mini App.
 *
 * Loads a flat JSON locale file and provides a t(key, params) function
 * with simple {placeholder} interpolation.
 *
 * Usage:
 *   await i18n.load("en");
 *   i18n.t("welcome", { name: "Alice" }); // "Hello, Alice!"
 */
var i18n = (function () {
  var _strings = {};
  var _locale = "en";

  /**
   * Load a locale JSON file from /miniapp/locales/{locale}.json.
   * Falls back to "en" if the requested locale is not available.
   */
  function load(locale) {
    _locale = locale || "en";
    var basePath = "locales/";
    return fetch(basePath + _locale + ".json")
      .then(function (res) {
        if (!res.ok) {
          if (_locale !== "en") {
            _locale = "en";
            return fetch(basePath + "en.json").then(function (r) {
              return r.json();
            });
          }
          return {};
        }
        return res.json();
      })
      .then(function (data) {
        _strings = data || {};
      })
      .catch(function () {
        _strings = {};
      });
  }

  /**
   * Look up a translation key with optional interpolation.
   *
   * @param {string} key - Dot-separated key (e.g. "settings.header")
   * @param {Object} [params] - Interpolation values (e.g. { name: "Alice" })
   * @returns {string} The translated string, or the raw key if not found.
   */
  function t(key, params) {
    var text = _strings[key];
    if (text === undefined) {
      return key;
    }
    if (params) {
      Object.keys(params).forEach(function (k) {
        text = text.split("{" + k + "}").join(String(params[k]));
      });
    }
    return text;
  }

  /** Return the currently loaded locale code. */
  function locale() {
    return _locale;
  }

  return {
    load: load,
    t: t,
    locale: locale,
  };
})();
