import jellyfish
import pandas as pd
import numpy as np
import string
import re
from unidecode import unidecode
from tqdm import tqdm
tqdm.pandas()
from collections import Counter
import time

CLUES_FILEPATH = 'test_output/clues_2023512-104755.csv'

#TODO: HAVE AN EMPIRICALLY DRIVEN TEST STRATEGY FOR FINDING THE BEST VALUES

qb_stopwords = {'a', 'an', 'and', 'of', 'the', 'this', 'these'}
more_stopwords = {'the', 'that', 'he', 'him', 'his', 'she', 'her', 'hers',
                   'is', 'are', 'work', 'works', 'who', 'which', 'was', 'were', 
                   'one', 'another', 'as', 'in', 'when', 'they', 'their', 'them',
                   'name', 'identify', 'man', 'mans', 'from', 'on', 'to', 'by',
                   'with', 'title', 'titular', 'those', 'it', 'its', 'be', 'at',
                   'as'}
indicator_stopwords = {'figure', 'figures', 'entity', 'entities', 'object',
                       'objects', 'substance', 'substances', 'character',
                       'characters'}
ans_stopwords = {'accept', 'prompt', 'reject', 'directed', 'antiprompt', 
                 'anti-prompt', 'or'}
all_stopwords = qb_stopwords | more_stopwords | indicator_stopwords
qb_punctuation = string.punctuation + '“”'

pd.set_option('display.max_colwidth', 1000)

#TODO: allow for making the term an answer / for subsetting by answerline
#rather than clue (to check "ziran/Iran" type cases)
def subset(clues_filepath, term, write_out=False):
    '''Generate subsets for similarity comparison.'''
    clues = pd.read_csv(clues_filepath, sep='\t')
    term = term.lower()
    #TODO: fix ValueError
    subset = clues.loc[(clues.loc[:,'clue'].str.contains(term, flags=re.IGNORECASE)), :]
    subset.reset_index(drop=True, inplace=True)
    write_filepath = f'subset_{term}.csv'

    if write_out:
        subset.to_csv(write_filepath, sep='\t', escapechar='\\', index=False)
    return subset


#see how many answer lines there are.
def unique_simple_answerlines(filepath=CLUES_FILEPATH):
    df = pd.read_csv(filepath, sep='\t')
    df.loc[:,'simple_answer'] = df.loc[:,'answer'].progress_apply(lambda x:distill(str(x), answerline=True))
    df.drop_duplicates(subset=['simple_answer'], inplace=True)
    df = df.sort_values('simple_answer', ascending=True)
    series = df.loc[:,'simple_answer']
    print(series)
    series.to_csv('unique_answers_0512.csv', sep='\t', escapechar='\\', index=False)


def distill(clue: str, answerline=False) -> str:
    '''Distill a clue or answer line down by removing stopwords, spaces, and
    punctuation to make string distance scores more robust.
    If it's an answer line, removes acceptable/promptable answers to expand
    range of matching.
    Makes string comparison scores more robust.'''
    if type(clue) != str:
        clue = str(clue)

    if answerline:
        #clue = re.sub(r'\(.+\)|\[.+\]', '', clue)
        REJECT_RE = r'(?:do not|don’t)\s(?:accept|prompt|take)\s|reject\s'
        # get rid of everything after reject/do not accept
        clue = re.split(REJECT_RE, clue)[0]

    try:
        clue = re.sub(r'[^\w\s\d]', '', unidecode(clue.lower()))
    except AttributeError: #it gets 'nan' sometimes which messes it up
        clue = re.sub(r'[^\w\s\d]', '', unidecode(clue.lower()))
    clue = [word for word in clue.split() if word not in qb_stopwords]
    if answerline:
        clue = [word for word in clue if word not in ans_stopwords]
    return ''.join(clue)


def wordify(clue: str, answerline=False):
    '''Convert a sentence/clue/answer into a set of unique non-stopword words.
    This prepares the input for Jaccard or overlap similarity comparisons.'''
    if answerline:
        #clue = re.sub(r'\(.+\)|\[.+\]', '', clue)
        REJECT_RE = r'(?:do not|don’t)\s(?:accept|prompt|take)\s|reject\s'
        # get rid of everything after reject/do not accept
        clue = re.split(REJECT_RE, clue)[0]
    '''Reduce a string of natural language text to a "bag of words" or set of
    the words it contains, removing common quizbowl stopwords.'''
    clue = re.sub(r'[^\w\s\d]', '', unidecode(clue.lower()))
    #consider doing some lemmatizing here
    word_set = {wd for wd in clue.split() if wd not in all_stopwords}
    if answerline:
        return {wd for wd in word_set if wd not in ans_stopwords}
    else:
        return word_set
    #This used to use a Counter but the odds of a word repeating are very low so it was of minimal benefit
    # counter = Counter([wd for wd in clue.split() if wd not in all_stopwords])
    # if counts:
    #     return counter
    # else:
    #     return set(counter.keys())
    

def jaccard(clue1, clue2, debug=False):
    '''Obtain the Jaccard similarity of two clues or answerlines.
    https://stats.stackexchange.com/questions/289400/quantify-the-similarity-of-bags-of-words'''
    bag1 = wordify(clue1)
    bag2 = wordify(clue2)

    shared = bag1 & bag2
    all = bag1 | bag2
    if debug:
        print(f"Shared: {shared}")
        print(f"Unique: {all - shared}")
    return len(shared) / len(all)


def jaccard_compare(clue1, clue2, debug=False):
    #figure out which threshold to set with trial and error
    return (jaccard(clue1, clue2, debug=debug) >= 0.5)


def overlap(clue1, clue2, debug=False):
    '''Calculate the overlap coefficient of two clues
    https://en.wikipedia.org/wiki/Overlap_coefficient'''
    bag1 = wordify(clue1)
    bag2 = wordify(clue2)

    shared = bag1 & bag2
    if debug:
        print(f"Shared: {len(shared)}")
        print(f"Bag 1 size: {len(bag1)}; Bag 2 size: {len(bag2)}")
    return len(shared) / min(len(bag1), len(bag2))


def overlap_compare(clue1, clue2, debug=False):
    #TODO: figure out which threshold to set with trial and error
    return (overlap(clue1, clue2, debug=debug) >= 0.6)

    
def comparator_test(
        func=jellyfish.jaro_distance,
        str1="Name this American poet of “Lady Lazarus,” “Daddy,” and The Bell Jar.",
        str2 = "Name this poet of “Ariel” and “Daddy” as well as The Bell Jar."
):
    return func(str1, str2)


def panda_comparison(clues_filepath, term='', start_at=None,
                     ANS_THRESH = 0.8, CLUE_THRESH = 0.6, 
                     clue_func=jellyfish.jaro_distance):
    '''Core function for finding repetitious clues and deleting them.
    Goes through each clue in the dataframe, uses Jaro-Winkler similarity (or
    other methods tbd) to block on close-matching answers, uses methods tbd
    to find close-matching clues with a similar enough answer, and marks those
    similar-enough rows for deletion. At the end, deletes the marked rows.

    #TODO: toggle progress bars
    
    Inputs:
        -clues_filepath(str): location of clues DataFrame in directory
        #TODO: Make this flexible to take in df from other sources
        -term (str): used for subsetting the DataFrame to look only at clues
        that contain this substring. Greatly increases runtime
        -start_at (str or None): used to subset the DataFrame to look only at
        answerlines that start after this point (e.g., 'start_at=aarom' allows
        for starting at the answer line 'Aaron'.)
        #TODO: Change this so it merely STARTS AT this answer rather than 
        DELETING prior rows
        
    Returns (df): the dataframe with repetitious rows deleted.'''
    df = subset(clues_filepath, term)
    print("Sorting dataframe by simplified answer line...")
    #TODO: allow for using wordify() instead of distill(), so as to allow for
    #overlap() later instead of jaro_distance
    df.loc[:,'simple_answer'] = df.loc[:,'answer'].progress_apply(lambda x:distill(str(x), 
                                                                  answerline=True))
    #Group all instances of each simplified answer line. This greatly reduces
    #runtime, by allowing us to calculate all matches for each simple answerline
    #only once, rather than each time the answerline appears.
    df = df.sort_values('simple_answer', ascending=False)
    if start_at is not None:
        df = df.loc[(df.loc[:,'simple_answer'] < start_at),:]
    df.reset_index(drop=True, inplace=True)
    df.loc[:,'clue_similarity'] = 0.0
    df.loc[:,'ans_similarity'] = 0.0
    prev_answer = None
    total_matches = 0
    for row in df.itertuples():
        print(row.Index, row.simple_answer)
        if df.loc[row.Index, 'clue'] == '_DEL_' or df.loc[row.Index, 'answer'] == '_DEL_':
            print(f"Row {row.Index} has been marked for deletion. Continuing")
            continue

        #TODO: look only at rows later than this one, to emulate "nested for loop" behavior
        #and cut runtime in half by ensuring each comparison happens only once
            # e.g. df.loc[row.Index+1:].loc[:, 'ans_similarity'] =
        if row.simple_answer != prev_answer: 
            # answer line has changed. recalculate. otherwise keep past calculation
            df.loc[:,'ans_similarity'] = df.loc[:,'answer'].apply(lambda x: jellyfish.jaro_distance(distill(str(x), answerline=True), 
                                                                                                            distill(str(row.answer), answerline=True)))

        #Answer similarity needs to have its own proper threshold determined. Consider things like middle names
        #TODO: Look at only rows later than this one
        ANS_MATCH_MASK = (df.loc[:,'ans_similarity'] > ANS_THRESH)

        df.loc[ANS_MATCH_MASK, 'clue_similarity'] = \
            df.loc[ANS_MATCH_MASK, 'clue'].apply(lambda x: clue_func(x, row.clue))
        
        #kludge so THIS row doesn't delete itself for perfectly matching itself
        df.loc[row.Index,'clue_similarity'] = 0.0
        df.loc[row.Index, 'ans_similarity'] = 0.0

        #TODO: keep testing if tweaks to this improve results
        CLUE_MATCH_MASK = (df.loc[:,'clue_similarity'] > CLUE_THRESH)
        DEL_MASK = ANS_MATCH_MASK & CLUE_MATCH_MASK

        #does latter option actually speed things up?
        #matches = df.loc[DEL_MASK, :] # Option 1
        matches = df.loc[row.Index:, :].loc[DEL_MASK, :] # Option 2

        if len(matches) > 0:
            print("One or more matches!")
            print(f"This clue: {row.clue}")
            print(matches)
            total_matches += len(matches)
            df.loc[DEL_MASK, 'clue'] = '_DEL_'
            df.loc[DEL_MASK, 'answer'] = '_DEL_'
        
        prev_answer = str(row.simple_answer)
    
    print(f'\n{len(df)}')
    print(f"{total_matches} MATCHING CLUES FOUND")
    df = df.loc[~(df.loc[:,'clue'] == '_DEL_'), :]
    print("...AND DELETED")
    print(f"{len(df)} CLUES REMAIN")

    return df


if __name__ == '__main__':
    print("Loading clue csv...")
    panda_comparison(CLUES_FILEPATH, term='love suicides', 
                     ANS_THRESH=0.7, CLUE_THRESH=0.6, 
                     clue_func=overlap)


