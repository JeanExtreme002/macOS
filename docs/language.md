# Language

{mod}`macos.language` detects the language and the sentiment of a text with
Apple's NaturalLanguage framework. It runs on the Mac, offline.

```python
import macos

macos.language.detect("Olá, tudo bem?")      # 'pt'
macos.language.sentiment("I love this!")     # 1.0
```

## Detecting the language

{func}`~macos.language.detect` returns an ISO code such as `'pt'`, `'en'`,
`'fr'` or `'zh-Hans'`, or `None` for empty text. {func}`~macos.language.guess`
shows how sure it is:

```python
macos.language.guess("Bonjour tout le monde")
# [('fr', 0.99), ('ca', 0.004), ('it', 0.002)]
```

A sentence is plenty, but a single word is often guessed wrong: check the
probability before trusting it.

## Sentiment

{func}`~macos.language.sentiment` scores how positive a text sounds, from
`-1.0` (very negative) to `1.0` (very positive):

```python
macos.language.sentiment("This is terrible and I hate it.")   # -1.0
macos.language.sentiment("Adorei, ficou ótimo!")              # 0.8
```

It's a rough signal, best for comparing texts such as reviews or messages: a
neutral sentence won't always score exactly 0.

## Reference

- {func}`macos.language.detect`
- {func}`macos.language.guess`
- {func}`macos.language.sentiment`
