import math

def dynamic_ans_thresh(n: int) -> float:
    '''
    Returns a Jaro-winkler similarity threshold for a simple answer string
    of length n, which is tighter (i.e. closer to 1) for shorter strings. This
    should speed up remove_redundancies(), because low Jaro-Winkler thresholds
    result in absurd numbers of spurious matches for short strings.

    TODO: more actual tests to set these boundaries and scores, or to find
    a gently-sloping function at the right rate with an asymptotic output
    at or a bit below 0.7 as n -> infty
    '''
    assert n > 0
    if n == 1:
        return 1.0
    elif n == 2:
        return 0.9
    elif n == 3:
        return 0.85
    elif n > 3 and n <= 6:
        return 0.8
    elif n > 6 and n <= 10:
        return 0.75
    elif n > 10 and n <= 20:
        return 0.73
    else:
        return 0.70

def dynamic_clue_thresh(n: int) -> float:
    '''
    Returns a set-overlap threshold for a clue-bag of size n, which is tighter
    (i.e. closer to total overlap) for short clue strings. 

    TODO: more actual tests to confirm that this is on the right track
    numbers-wise. Note that as-is, this can be higher for n+1 than it is for n
    '''
    if n <= 3:
        return 1.0
    else:
        return (math.floor(n/2) + 1.0) / n