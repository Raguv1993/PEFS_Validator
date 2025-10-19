from rapidfuzz import fuzz
import pandas as pd

def build_context(df, target_prefix, radius=100):
    """
    Build text context windows around each target tag.
    Returns DataFrame with tag text and surrounding words.
    """
    contexts = []
    for i, tag in df[df["text"].str.startswith(target_prefix, na=False)].iterrows():
        # texts nearby in distance 'radius'
        same_page = df[df["page"] == tag["page"]]
        neighbors = same_page[
            (abs(same_page["x0"] - tag["x0"]) <= radius)
            & (abs(same_page["y0"] - tag["y0"]) <= radius)
        ]
        context_words = " ".join(neighbors["text"].tolist())
        contexts.append({"text": tag["text"], "context": context_words})
    return pd.DataFrame(contexts)

def find_best_match(tag_row, df_context2, threshold=75):
    """
    Compare one tag + context from Drawing 1 against all from Drawing 2.
    """
    best_row, best_score = None, 0
    for _, cand in df_context2.iterrows():
        score = fuzz.partial_ratio(tag_row["context"], cand["context"])
        if score > best_score:
            best_row, best_score = cand, score
    return best_row, best_score if best_score >= threshold else (None, 0)
