# questions_to_cards
Scripts for converting bulk collections of quizbowl questions, such as folders of [packets](https://quizbowlpackets.com) or [QBReader](https://www.qbreader.org/db) backup .json files, into .csv files formatted for import as [Anki](https://apps.ankiweb.net) digital flashcards at the clue level.

## Background

Many competitors in knowledge contest games, such as [quizbowl](https://www.qbwiki.com/wiki/Main_Page), use digital flashcard apps and/or [spaced repetition](https://ncase.me/remember/) to aid in memorizing lots of information. In many cases, the most useful information to learn for future success is the content of past questions -- i.e. there is a loose "[canon](https://www.qbwiki.com/wiki/Canon)" of topics that, if anticipated and studied, are extremely likely to result in improved performance.

Building a collection of useful flashcards can be difficult -- creating new flashcards can be time-consuming, existing decks sourced from the Internet might not focus on the right material, and other competitors are often reluctant to trade or give away the decks they've put in their own effort to assemble. Past quizbowl questions are long, and contain text formatted for gameplay that can be distracting. 

## Intended program flow
(*italics: aspirational/"reach goal"*)

When executed, the module should:

- Ingest a collection of quizbowl questions from a specified filepath (.pdf file, .docx file, folder of .pdf and/or .docx files, QBReader backup `tossups.json` and/or `bonuses.json`),
    - *For category-labeled input: let user narrow down to specific categories (`Science`, e.g.) (or difficulty ratings, release years, etc.)*
- Pre-process text to isolate proper boundaries between cogent clue-sentences (usually, sentence-final periods) and prevent splitting elsewhere (e.g. at ellipses)
- Split each question into cogent clue-sentences, with each clue-sentence paired with its answer; stack those clue-answer pairs as a pandas DataFrame
- Post-process the DataFrame to remove obvious non-clues, drop duplicates, clean up clue and answer line formatting, etc.
    - *For large DataFrames where multiple questions have the same/similar answer: use fuzzy matching to remove near-duplicate rows*
    - *For small DataFrames: give user a chance to look over the table and manually delete unneeded rows (i.e. clues they don't need a card for*)
- If possible, keep a column of metadata (question release year, category, etc.) to be read in as [Anki tags](https://docs.ankiweb.net/editing.html?highlight=tags#using-tags)
- Write out the final DataFrame to a .csv file, for import to Anki (*and allow for auto-upload to Anki on one's system*)

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

### Tagstrings

An Anki card can have an arbitrary number of tags, which can be used to organize cards or filter while browsing one's card collection. The organization system is hierarchical, with a double colon (`::`) indicating that the string to the right is a sub-tag of the string to the left. For example, if Card A has tag `cat::Science::Biology` and Card B has tag `cat::Science::Chemistry`, both cards will appear in Anki browse results if the user filters to cards with the tag `Science`, but only Card A will appear if the user filters to cards tagged `Biology`.

When Anki imports have a Tags column, each entry in that column is a string, in which different tags are separated by a single space. So, to preserve the information about a clue's category, difficulty, release year, source, and type, it might be imported with a tagstring like: 
- `cat::Science::Other_Science diff::3 source::2020_MOQBA_Novice type::tossup yr::2020` (example tossup)

Depending on input source, it may not be possible to obtain all this information. (*In recent years, it has become standard for questions to have a category label and/or author credit after the last answerline; input directly from packet files will seek to extract that information. Additionally, users may be asked from the command line if a specified difficulty, category, release year, etc. should be applied to all cards in the file.*)

## A note on size and efficiency

As of July 7, 2023, QBReader contains "248,818 questions from 474 sets." As of April 30, 2023, the `bonuses.json` backup file is 169.5 MB and the `tossups.json` backup file is 182.8 MB. When split at the clue-sentence level, this produces almost _1.3 million_ unique cards; the resultant .csv is 309.7 MB. These sizes will only grow as more questions are added to QBReader.

This is more cards than any individual can possibly learn. Having this many cards in Anki causes hang-time delays of several seconds when doing basic things such as "open the Browse window", and produces a database so large that it cannot be synced on AnkiWeb (which has a 300MB size limit).

What's more, even after exact duplicates are removed, large datasets of clues contain many inexact matches and are highly repetitious. Consider, for example, this (very incomplete) list of clues about the Spanish Civil War:

- `During this conflict, the Condor Legion conducted an infamous air raid on the Basque town of Guernica.` *(source: 2022 ACF Fall)*
- `During this war, the German Condor Legion bombed the Basque city of Guernica.` *(source: 2021 Spring Novice)*
- `During this war, the Nazis’ Condor Legion bombed the civilian town of Guernica.` *(source: 2018 Bulldog High School Academic Tournament)*
- `German intervention during this conflict led to the Condor Legion’s bombing of the Basque town of Guernica.` *(source: 2015 Maryland Fall)*

Note also this clue, whose answer is "Francisco Franco":

- `At this leader’s behest, the Nazis’ Condor Legion carried out the 1937 brutal bombing of Guernica.`

Because [spaced repetition](https://ncase.me/remember/) already results in users seeing a clue in inverse frequency to the user's mastery of that particular clue, the user needs at most one card with this basic idea on it; all others are redundant and should be deleted.

This is, in essence, a [record linkage](https://en.wikipedia.org/wiki/Record_linkage) problem where both inputs are the same list. Naive record linkage has a runtime complexity of $O(n^2)$; with a list of over 1 million clues, that'd require over 1 trillion pairwise clue comparisons, which is not tractable in practical amounts of time on standard consumer hardware (in my case, a 2022 MacBook Air with M1 Apple silicon and 16GB RAM).

A standard solution for increasing efficiency is to implement [blocking](https://en.wikipedia.org/wiki/Record_linkage#Probabilistic_record_linkage) on the `answer` column before using fuzzy matching methods on clues that share an answer. However, in this case, the blocking itself must be somewhat fuzzy, as answerline formatting is not standardized across all question sets (ignoring bolding and underlining, you might have `Spanish Civil War`, `Spanish Civil War [or Guerra Civil Española]`, `Spanish Civil War (accept Guerra Civil Espan ̃ola)`, `Spanish Civil War [or Guerra Civil Española; prompt on Guerra Civil or La Guerra]`, or `Spanish Civil War [prompt on War in Spain]`.
- In other cases, you may have transposed names (e.g. `Jun’ichirō Tanizaki` and `Tanizaki Jun’ichirō]` are the same person). 

Even with fuzzy blocking on answer, it seems this deduplication process is likely to take several days to run, and will have many Type I and Type II errors. *Increasing the efficiency of this process, and finding the right methods and similarity scores to minimize its error rate, is a high priority.*

## A note on limitations

Use the flashcards derivable from this library *at your own risk.* Many past questions either contain factual errors or are out of date -- this code cannot fact-check past material for you or attest to its veracity.

Additionally, some clues might not make sense in isolation -- consider, e.g., 
- antecedent references (e.g. “Another character in this play gives that character a sleeping potion”)
- non-unique sentences (e.g. “Name this Japanese author.”)
- statements of opinion (e.g. “Unfortunately, it failed.”)
- gameplay directives and clarifying non-clue text (e.g. “Note to players: composer and genre required.”) *(a layer of post-processing will remove the most common text strings of this sort)*


Additionally, QBReader uses a naive Bayes classifier to assign questions to categories (with human reports/reviews of individual misclassified questions); this classifier has a substantial error rate (upon information and belief, its accuracy is about 80%). Getting all questions labeled `Science` by QBReader, e.g., will contain some false positives (questions labeled `Science` that aren't about science) and omit some false negatives (questions that are about science, but were given another label such as `Literature`).
