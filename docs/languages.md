Kolibri Language Codes
----------------------

The file [le_utils/constants/languages.py](https://github.com/learningequality/le-utils/blob/master/le_utils/constants/languages.py)
and the lookup table in [le_utils/resources/languagelookup.json](https://github.com/learningequality/le-utils/blob/master/le_utils/resources/languagelookup.json)
define the internal representation for languages codes used by Ricecooker, Kolibri,
and Kolibri Studio to identify content items in different languages.

The internal representation uses a mixture of two-letter codes (e.g. `en`),
two-letter-and-country code (e.g. `pt-BR` for Brazilian Portuguese),
and three-letter codes (e.g., `zul` for Zulu).

In order to make sure you have the correct language code when interfacing with
the Kolibri ecosystem (e.g. when uploading new content to Kolibri Studio), you
must lookup the language object using the helper method `getlang`:

```
>>> from le_utils.constants.languages import getlang
>>> language_obj = getlang('en')       # lookup language using language code
>>> language_obj
Language(native_name='English', primary_code='en', subcode=None, name='English', ka_name=None)
```
The function `getlang` will return `None` if the lookup fails. In such cases, you
can try lookup by name or lookup by alpha2 code (ISO_639-1) methods defined below.

Once you've successfully looked up the language object, you can obtain the internal
representation language code from the language object's `code` attribute:
```
>>> language_obj.code
'en'
```
The `ricecooker` API expects these internal representation language codes will be
supplied for all `language` attributes (channel language, node language, and files language).



### More lookup helper methods

The helper method `getlang_by_name` allows you to lookup a language by name:
```
>>> from le_utils.constants.languages import getlang_by_name
>>> language_obj = getlang_by_name('English')  # lookup language by name
>>> language_obj
Language(native_name='English', primary_code='en', subcode=None, name='English', ka_name=None)
```

The module `le_utils.constants.languages` defines two other language lookup methods:
  - Use `getlang_by_native_name` for lookup up names by native language name,
    e.g., you look for 'Français' to find French.
 -  Use `getlang_by_alpha2` to perform lookups using the standard two-letter codes
    defined in [ISO_639-1](https://en.wikipedia.org/wiki/ISO_639-1) that are
    supported by the `pycountries` library.
