# questions_to_cards
Scripts for converting bulk collections of quizbowl questions, such as folders of [packets](https://quizbowlpackets.com) or [QBReader](https://www.qbreader.org/db) backup .s, into .csv files formatted for import as [Anki](https://apps.ankiweb.net) digital flashcards at the clue level.

## Background

Many competitors in knowledge contest games, such as [quizbowl](https://www.qbwiki.com/wiki/Main_Page), use digital flashcard apps and/or spaced repetition to aid in memorizing lots of information. In many cases, the most useful information to learn for future success is the content of past questions -- i.e. there is a loose "[canon](https://www.qbwiki.com/wiki/Canon)" of topics that can be anticipated.

Building a collection of useful flashcards can be difficult -- creating new flashcards can be time-consuming, existing decks sourced from the Internet might not focus on the right material, and other competitors are often reluctant to trade or give away the decks they've put in their own effort to assemble. Past quizbowl questions are long, and contain text formatted for gameplay that can be distracting. 

## Intended program flow

*TK*

### Example tossup question

```
This programming language’s Django framework is used for web development, while its BeautifulSoup library scrapes
data from websites. Pip is a package manager for this language. Data scientists use this language’s “pandas,”
“num,” and “sci” libraries. This language, which does not require the use of (*) semicolons after each statement,
uses indents to denote code blocks as opposed to curly braces. For 10 points, name this easy-to-read programming
language that isn’t actually named for a snake.
ANSWER: Python
```
*(Source: 2020 MOQBA Novice tournament)*

Here is the same tossup question, split up into a table with one clue per row:

|Clue |Answer|
|-----|------|
|This programming language’s Django framework is used for web development, while its BeautifulSoup library scrapes data from websites. |Python|
|Pip is a package manager for this language. |Python|
|Data scientists use this language’s “pandas,” “num,” and “sci” libraries. |Python|
|This language, which does not require the use of semicolons after each statement, uses indents to denote code blocks as opposed to curly braces. |Python|
|Name this easy-to-read programming language that isn’t actually named for a snake. |Python|

Note that the "power mark" (`(*)`) is not included, and the phrase "For 10 points," is omitted from the last clue (the "giveaway").


### Example bonus question

```
For 10 points each, answer the following about different “merges” in computer science.
[10] Merge is a divide-and-conquer algorithm for this task, which puts some collection of elements in order.
ANSWER: sorting [accept mergesort]
[10] In the Git version control software, merge is used to combine commits made on these entities. The checkout
command is used to switch between these entities.
ANSWER: branches
[10] The merge command is used in a “structured” language to insert, update, or delete in the relational type of
these systems. Transactions in these systems should obey the ACID (“acid”) properties.
ANSWER: databases [or DBs; accept relational databases] (The language is Structured Query Language, or SQL.)
```
*(source: 2022 ACF Fall)*

Here is the same bonus question, split up into a table with one clue per row:

|Clue |Answer|
|-----|------|
|Merge is a divide-and-conquer algorithm for this task, which puts some collection of elements in order.| sorting \[accept mergesort\]|
|In the Git version control software, merge is used to combine commits made on these entities.|branches|
|The checkout command is used to switch between these entities.|branches|
|The merge command is used in a “structured” language to insert, update, or delete in the relational type of these systems.|databases \[or DBs; accept relational databases\]|
|Transactions in these systems should obey the ACID properties.|databases \[or DBs; accept relational databases\]|


Note: in this case, the first line of the bonus (the "leadin") is omitted because it's not a clue referring to any particular answer. However, in some cases the leadin is a substantive clue about the first answer; in those cases, it is included.
Also note: the pronunciation guide for ACID is not included.

## A note on limitations

Use the flashcards derivable from this library *at your own risk.* Many past questions either contain factual errors or are out of date -- this code cannot fact-check past material for you or attest to its veracity.

Additionally, some clues might not make sense in isolation -- consider, e.g., 
- antecedent references (e.g. “Another character in this play gives that character a sleeping potion”)
- non-unique sentences (e.g. “Name this Japanese author.”)
- statements of opinion (e.g. “Unfortunately, it failed.”)
- gameplay directives and clarifying non-clue text (e.g. “Note to players: composer and genre required.”) *(a layer of post-processing will remove the most common text strings of this sort)*


Additionally, QBReader uses a naive Bayes classifier to assign questions to categories (with human reports/reviews of individual misclassified questions); this classifier has a substantial error rate. Getting all questions labeled "Science" by QBReader, e.g., will contain some false positives (questions labeled Science that aren't about science) and omit some false negatives (questions that are about science, but were given some other label, such as Literature).
