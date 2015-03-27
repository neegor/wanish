

## About

This package allows you to summarize text by reducing an article in size to several sentences retaining the idea of the text.

Besides of that the package extracts the following from the document:

1. Canonical URL of the article
2. Title of the article
3. URL of the image characterizing this article
4. Strips the document of excessive information (headers, footers, navigation, advertisement, etc.) and forms a clean HTML based on structured data of schema.org

[DEMO](http://reefeed.com)

## Installation

```
easy_install wanish
or
pip install wanish
```

## Usage

```python
from wanish import Wanish
wanish = Wanish()
wanish.perform_url(document_url)

# getting doc's source canonical url
url = wanish.url
# getting document's title
title = wanish.title
# getting url of related image if document has it
image_url = wanish.image_url
# getting two-letter code of the document's language (en, de, es...)
language_code = wanish.language
# getting a clean html page of a document with article
clean_html = wanish.clean_html
# getting a short summarized description of the article reduced to several sentences (5 by default)
description = wanish.description
```

Available kwarg options for _Wanish()_ class (all are optional):

```python
wanish = Wanish(url=document_url,
                positive_keywords=["main", "story"],
                negative_keywords=["banner", "adv", "similar", "top-ad"],
                summary_sentences_qty=5,
                headers={'user-agent': 'test-purposes/0.0.1'})
```

* **url:** Allows to pass an url of a document in constructor. If set, then it will automatically launch _self.perform_url(url)_ after initialization. Default is None.
* **positive_keywords:** A list of positive search patterns in classes and ids, for example: _["main", "story"]_ . Default is None.
* **negative_keywords:** A list of negative search patterns in classes and ids, for example: _["banner", "adv", "similar", "top-ad"]_ . Default is None.
* **summary_sentences_qty:** Maximum quantity of sentences in summarized text of the document. Set to 5 by default.
* **headers:** Dict of additional custom headers for GET request to obtain web page of the article. Default is None.

## Special Thanks

* https://github.com/nltk/nltk
* https://github.com/buriy/python-readability
* https://github.com/saffsd/langid.py

http://www.apache.org/licenses/LICENSE-2.0