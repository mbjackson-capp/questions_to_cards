import pandas as pd
import numpy as np
import string
import re
from unidecode import unidecode
from tqdm import tqdm
tqdm.pandas()
from collections import Counter
import spacy
import batch_jaro_winkler as bjw # by Dominik Bousquet, https://github.com/dbousque/batch_jaro_winkler
from dynamic_threshes import ans_thresh_hashtable, dynamic_clue_thresh

nlp = spacy.load("en_core_web_sm", exclude=["parser", "ner"])

CLUES_FILEPATH = 'test_output/clues_2023512-104755.csv'

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

pd.set_option('display.max_colwidth', 400)


def subset(clues, ans_term=None, clue_term=None, write_out=False):
    '''
    Generate subsets of a DataFrame for quicker similarity comparison.

    Inputs:
        - clues (string or DataFrame): can take a filepath string to import
        from filepath; otherwise, take an existing DataFrame of clues
        - ans_term (string or None): term that must be in answer line upon
        filtering.
        - clue_term (string or None): term that must be in clue upon
        filtering. As of now, ans_term filter is applied FIRST, and having
        a non-null value for both ans_term and clue_term produces the strict
        INTERSECTION in which both are present.
        #TODO: Consider altering behavior to allow for UNION/OR.
        - write_out (boolean): whether to write to file or not.

    Returns (pandas DataFrame): the subset you want.
    '''
    if type(clues) == str:
        clues = pd.read_csv(clues, sep='\t')

    assert type(clues) == pd.core.frame.DataFrame, "You don't have a working df"
    # TODO: fix ValueError
    if ans_term is None and clue_term is None:
        return clues

    subset = clues

    if ans_term is not None:
        ans_term = ans_term.lower()
        print(ans_term)
        subset = subset.loc[(subset.loc[:, 'answer'].str.contains(ans_term, flags=re.IGNORECASE)) &
                            (~subset.loc[:, 'answer'].isna()), :]  # some answers are 'nan'
        subset.reset_index(drop=True, inplace=True)
    if clue_term is not None:
        print(clue_term)
        clue_term = clue_term.lower()
        subset = subset.loc[(subset.loc[:, 'clue'].str.contains(clue_term, flags=re.IGNORECASE)), :]
        subset.reset_index(drop=True, inplace=True)

    if write_out:
        write_filepath = f'subset_{ans_term}_{clue_term}.csv'
        subset.to_csv(write_filepath, sep='\t', escapechar='\\', index=False)
    return subset


def distill(
        phrase: str,
        answerline=False,
        remove_brackets=True,
        lemmatize=False,
        max_length=50) -> str:
    '''
    Distill a clue or answer line down by removing stopwords, spaces, and
    punctuation to make Jaro-Winkler string distance score more robust.
    If it's an answer line, removes acceptable/promptable answers to expand
    range of matching.
    '''
    if type(phrase) != str:
        phrase = str(phrase)

    if answerline:
        REJECT_RE = r'(?:do not|don’t)\s(?:accept|prompt|take)\s|reject\s'
        # get rid of everything after reject/do not accept
        phrase = re.split(REJECT_RE, phrase)[0]

    if remove_brackets:
        phrase = re.sub(r'\[[^\[]+\]|\([^\(]+\)|{[^\{]+}', '', phrase)

    try:
        phrase = re.sub(r'[^\w\s\d]', '', unidecode(phrase.lower()))
    except AttributeError:  # it gets 'nan' sometimes which messes it up
        phrase = re.sub(r'[^\w\s\d]', '', unidecode(phrase.lower()))
    phrase = [word for word in phrase.split() if word not in qb_stopwords]
    if answerline:
        phrase = [word for word in phrase if word not in ans_stopwords]

    #Source: https://www.machinelearningplus.com/nlp/lemmatization-examples-python/
    if lemmatize:
        doc = nlp(' '.join(phrase))
        distilled_phrase = ''.join([token.lemma_ for token in doc])
    else:
        distilled_phrase = ''.join(phrase)

    if len(distilled_phrase) > max_length:
        distilled_phrase = distilled_phrase[:max_length + 1]

    return distilled_phrase


def wordify(clue: str, answerline=False, lemmatize=False):
    '''
    Convert a sentence/clue/answer into a set of unique non-stopword words.
    This prepares the input for Jaccard or overlap similarity comparisons.
    '''
    if answerline:
        REJECT_RE = r'(?:do not|don’t)\s(?:accept|prompt|take)\s|reject\s'
        # get rid of everything after reject/do not accept
        clue = re.split(REJECT_RE, clue)[0]

    clue = re.sub(r'[^\w\s\d]', '', unidecode(clue.lower()))

    if lemmatize:
        doc = nlp(clue)
        word_set = {token.lemma_ for token in doc}
        word_set = {wd for wd in word_set if wd not in all_stopwords}
    else:
        word_set = {wd for wd in clue.split() if wd not in all_stopwords}

    if answerline:
        return {wd for wd in word_set if wd not in ans_stopwords}
    else:
        return word_set


def remove_redundancies(
        clue_df,
        max_ans_len=50,
        ans_term=None,
        clue_term=None,
        skip_thresh=None,
        ans_thresh=0.7,
        clue_thresh=0.6,
        dynamic_threshes=True,
        simplify_answers=True,
        lemmatize=False,
        asc=True
):
    '''
    Most up-to-date function for finding repetitious clues and deleting them
    to minimize redunancy in final deck of cards.

    Starts by creating a simplified answer line and calculating the "bag size"
    (number of unique non-stopword words in the clue) for all rows.

    Then, for each row of the dataframe, uses Pandas selectors and vectorized
    .apply() to do the following:
        - "Block" on fuzzy-matching answer lines by finding LATER rows whose
        answer line has a high enough Jaro-Winkler similarity score to current row.
        -Within those, find rows whose clue has high enough word overlap with
        current row.
        - Mark current row for deletion if any high-word-overlap clue below this
        one is longer than current row (to preserve card with maximal information).
        - Mark any row with fuzzy-matching answer and high-word-overlap clue for
        deletion if that row's clue is shorter than current row (to delete redundancies).

    Inputs:
        - clues_filepath (str or DataFrame): location of clues DataFrame in directory
        or the DataFrame itself.
        - ans_term (str): used for subsetting the DataFrame to look only at answer
        lines that contain this substring. Greatly increases runtime.
        - clue_term (str): used for subsetting the DataFrame to look only at clues
        that contain this substring. Greatly increases runtime.
        - skip_thresh (int or None): if an integer, represents the minimum number
        of occurrences a simple answer should have in order to be evaluated. For
        example, if skip_thresh == 3, the function will not recalculate similarity
        scores for simple answers that occur only 2 times or 1 time in the
        underlying df. This saves time when the clue df is large and full of
        relatively rare answer lines that are unlikely to have matching clues.
        - ans_thresh (float): threshold value for answer similarity score, above
        which two answers will be considered to match.
        - clue_thresh (float): thresold value for clue similarity score, above
        which two clues will be considere close enough to mark the shorter one
        for deletion.
        - simplify_answers (boolean): Determines whether answers are simplified
        prior to comparison. Should be set to True.
        - asc (boolean): Determines whether simplified answer lines are sorted
        alphabetically (0-Z, True) or in reverse alphabetical order (Z-0, False).

    Returns (df): the dataframe with repetitious rows deleted.
    '''
    if dynamic_threshes:
        print("DYNAMIC THRESHOLD-SETTING IS ON")
        ALL_ANS_THRESHES = ans_thresh_hashtable(max_ans_len+1)

    if ans_term is not None or clue_term is not None:
        print("Subsetting dataframe...")
    df = subset(clue_df, ans_term, clue_term)

    if "simple_answer" not in df.columns:
        print("Generating simplified answer lines for every row...")
        if simplify_answers:
            df.loc[:,'simple_answer'] = df.loc[:,'answer'].progress_apply(
                lambda x:distill(str(x), 
                                 answerline=True,
                                 max_length = max_ans_len,
                                 lemmatize=lemmatize)
                )
        else:
            df.loc[:,'simple_answer'] = df.loc[:,'answer']

    print("Counting frequency of each simplified answer...")
    simple_ans_freqs = Counter(df.loc[:, 'simple_answer'])
    #TODO: You probably want to create an ans_len column here instead of calculating
    # each time you have a new similarity threshold.

    print("generating clue bag...")
    df.loc[:, 'clue_bag'] = df.loc[:, 'clue'].progress_apply(
        lambda x: wordify(x, lemmatize=lemmatize)
        )

    if "bag_size" not in df.columns:
        print("Calculating number of unique words in each clue...")
        df.loc[:,'bag_size'] = df.loc[:,'clue_bag'].progress_apply(len)

    # greatly reduce runtime, by allowing us to calculate all matches for each
    # simple answerline only once.
    print("Sorting database...")
    df = df.sort_values(by=['simple_answer', 'clue'], ascending=asc)
    df = df.dropna(how="any", subset=["answer", "simple_answer"]).reset_index(drop=True)

    print("Generating numeric_clue_bag table...")
    bag_size_numpy = df["bag_size"].to_numpy()
    word_counter = Counter()
    for clue_bag in df["clue_bag"]:
        word_counter.update(clue_bag)
    all_word_arr = np.sort(np.array([word for word in word_counter.keys()]))
    numeric_clue_bag = np.zeros((len(df), np.amax(bag_size_numpy)), dtype=int)-1
    for clue_i, clue_bag in enumerate(tqdm(df["clue_bag"])):
        word_to_idx = np.searchsorted(all_word_arr, np.array(list(clue_bag)))
        numeric_clue_bag[clue_i, :len(word_to_idx)] = word_to_idx

    df.loc[:, 'ans_similarity'] = -1.0
    df.loc[:, 'clue_similarity'] = -1.0

    print("Preparing for batch Jaro-Winkler similarity score calculation...")
    # this line breaks if I don't dropna (if "nan" is an answer). TODO: fix
    unique_strs, unique_idxs = np.unique(df[["simple_answer"]].to_numpy().flatten(), return_inverse=True)
    exp_model = bjw.build_exportable_model(unique_strs.flatten())
    rt_model = bjw.build_runtime_model(exp_model)

    # re-order Jaro-Winkler results from original sort order (based on length)
    init_bjw_result = bjw.jaro_distance(rt_model, "_")
    bjw_order_strs = np.array([result_tuple[0] for result_tuple in init_bjw_result])
    bjw_order_to_alphabetical_idxs = np.argsort(bjw_order_strs)

    # initialize variables
    prev_answer = None
    rows_marked_del = 0
    ans_similarity_bin = np.full((len(df),), False)
    deleted_rows = set()

    for row_tuple in df.itertuples():
        print(f"\nNOW CONSIDERING ROW {row_tuple.Index}.")
        if row_tuple.Index in deleted_rows:
            print(f"Row {row_tuple.Index} has been marked for deletion. Continuing")
            continue
        else:
            print(f"answer: {row_tuple.simple_answer}")

        this_ans_freq = simple_ans_freqs[row_tuple.simple_answer]
        if skip_thresh is not None and this_ans_freq < skip_thresh:
            print(f"This answer occurs only {this_ans_freq} times. Not often enough to calculate scores")
            print("Skipping")
            continue

        if row_tuple.simple_answer != prev_answer:
            # Recalculate similarity scores
            bjw_result = bjw.jaro_distance(rt_model, row_tuple.simple_answer)
            unique_res_vals = np.array([result_tuple[1] for result_tuple in bjw_result])[bjw_order_to_alphabetical_idxs]
            if dynamic_threshes:
                ans_thresh = ALL_ANS_THRESHES[len(row_tuple.simple_answer)]
                print(f"New similarity threshold for {row_tuple.simple_answer} = {ans_thresh}")
            # Find which rows have answer with a high enough similarity score
            ans_similarity_bin = (unique_res_vals > ans_thresh)[unique_idxs]
            prev_answer = row_tuple.simple_answer

        # make ans_similarity_bin (ans_similarity > ans_thresh) & (index > row_idx)
        ans_similarity_bin[:row_tuple.Index+1] = False

        df_subset = df.loc[ans_similarity_bin, :]
        # Within that, find matching clues by calculating overlap coefficients
        # between this row's clue and each other clue (speedily, using numpy)
        # See https://en.wikipedia.org/wiki/Overlap_coefficient
        shared_words = np.sum(np.isin(numeric_clue_bag[ans_similarity_bin, :], numeric_clue_bag[row_tuple.Index, :row_tuple.bag_size]), axis=1)
        min_vals = np.minimum(row_tuple.bag_size, bag_size_numpy[ans_similarity_bin])

        # work around numpy ZeroDivisionWarning:
        # set the 0s to 1000 then set the clue overlap to 1 eventually
        min_vals[min_vals<1] = 1000
        clue_overlap_vals = shared_words/min_vals
        clue_overlap_vals[min_vals==1000] = 1
        if dynamic_threshes:
            clue_thresh = dynamic_clue_thresh(row_tuple.bag_size)
            print(f"Similarity threshold for this clue: {clue_thresh}")
        CLUE_MATCH_MASK = clue_overlap_vals > clue_thresh

        if CLUE_MATCH_MASK.sum() > 0:
            # within those, get strictly shorter clues
            print(f"This clue: {row_tuple.clue_bag}")
            SMALLER_MASK = (df_subset.loc[:, 'bag_size'] < row_tuple.bag_size)
            DEL_MASK = ~df_subset.index.isin(deleted_rows)
            SMALLER_SUBSET_MASK = CLUE_MATCH_MASK & SMALLER_MASK & DEL_MASK
            if (num_subset_del := SMALLER_SUBSET_MASK.sum()) > 0:
                # mark all such rows for deletion
                print(f"{num_subset_del} rows ready to be marked for deletion")
                print(df_subset.loc[SMALLER_SUBSET_MASK, :])
                deleted_rows.update(df_subset.index[SMALLER_SUBSET_MASK])
                rows_marked_del += num_subset_del
            else:
                print("NO MATCHING CLUES OF SMALLER LENGTH FOUND")

            # within those, check for ANY strictly longer clue
            BIGGER_MASK = (df_subset.loc[:, 'bag_size'] > row_tuple.bag_size)
            BIGGER_SUBSET_MASK = CLUE_MATCH_MASK & BIGGER_MASK
            if BIGGER_SUBSET_MASK.sum() > 0:
                print("THIS ROW IS SHORTER THAN A MATCHING CLUE. MARKING IT FOR DELETION...")
                print("(For reference, here is a LONGER row we are KEEPING:)")
                print(df_subset.loc[BIGGER_SUBSET_MASK, :].sample(1))
                deleted_rows.update([row_tuple.Index])
                rows_marked_del += 1

        print(f"Rows marked for deletion so far: {rows_marked_del}")

    assert rows_marked_del == len(deleted_rows)
    print(f"{rows_marked_del} total rows marked for deletion")
    deleted_rows_mask = df.index.isin(deleted_rows)
    df = df.loc[~deleted_rows_mask, ["clue", "answer", "tags"]]
    print("Redundant row deletion complete")
    return df


if __name__ == '__main__':
    print("Loading clue csv...")
    CLUES_FILEPATH = "clues_sample100_092023.csv"
    clues = pd.read_csv(CLUES_FILEPATH, sep="\t")
    ans_input = input("Choose phrase to filter answer line by, or type Enter to continue:")
    if ans_input == '':
        ans_input = None
    clue_input = input("Choose phrase to filter clues by, or type Enter to continue:")
    if clue_input == '':
        clue_input = None
    print("Do you want to lemmatize answers and clues?")
    lemmatize_input = input("This will GREATLY INCREASE runtime and is STRONGLY DISCOURAGED.")
    if lemmatize_input in ["yes", "y", True, 1]:
        lemmatize_input = True
    else:
        lemmatize_input = False 
    df = remove_redundancies(
        clues, 
        ans_term=ans_input,
        clue_term=clue_input, 
        skip_thresh=3,
        lemmatize=lemmatize_input
        )
    print(f"Actual length of new dataframe is: {len(df)}")