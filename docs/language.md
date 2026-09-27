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

## Similar meanings

{func}`~macos.language.similarity` scores how close two texts are in meaning,
from -1.0 to 1.0. Compare scores with each other: a value alone means little.

```python
question = "How do I change my password?"
macos.language.similarity(question, "I forgot the password of my account")   # 0.10
macos.language.similarity(question, "What time does the store open?")        # 0.04
```

Two single words use a word model; anything longer, a sentence model. Pass
`language` for single words or very short texts: detecting it needs a few
words, and "car automobile" alone reads as French.

```python
macos.language.similarity("carro", "automóvel", language="pt")   # 0.17
macos.language.similarity("carro", "banana", language="pt")      # -0.27
```

Opposites such as "happy" and "sad" often score as related, because they show
up in similar sentences.

## Embeddings

{func}`~macos.language.embedding` turns a text into a vector of numbers that
represents its meaning. Store the vectors of many texts to search them by
meaning, offline:

```python
import math

def cosine(a, b):
    return sum(x * y for x, y in zip(a, b)) / (math.hypot(*a) * math.hypot(*b))

notes = ["Buy milk and eggs", "Call the dentist", "Renew the passport"]
vectors = [macos.language.embedding(note, language="en") for note in notes]
query = macos.language.embedding("groceries", language="en")
print(max(zip(notes, vectors), key=lambda pair: cosine(query, pair[1]))[0])
```

Only vectors from the same language can be compared.

## Names of people, places and organizations

```python
macos.language.entities("Tim Cook visitou São Paulo com a Apple ontem.")
# [Entity(text='Tim Cook', kind='person', start=0),
#  Entity(text='São Paulo', kind='place', start=17),
#  Entity(text='Apple', kind='organization', start=33)]
```

`start` is where the name begins in the text. It's a statistical model: common
names are found reliably, unusual ones can be missed.

## Reference

- {func}`macos.language.detect`
- {func}`macos.language.guess`
- {func}`macos.language.sentiment`
- {func}`macos.language.similarity`
- {func}`macos.language.embedding`
- {func}`macos.language.entities`
- {class}`macos.language.Entity`
