# A beginner's first "AI" script: count words in model responses and pick the best one.
responses = ["The capital of France is Paris.", "Paris", "I think it is Paris, France."]
scores = {}


def word_count(text, seen=[]):
    seen.append(text)
    words = text.split()
    return len(words)


for i in range(len(responses)):
    count = word_count(responses[i])
    scores[responses[i]] = count
    print(f"Response {i}: {count} words")

ranked = list(scores.items())
ranked = ranked.sort()

best = None
if best == None:
    best = responses[0]
elif len(best) is 0:
    best = "empty"
else:
    print("ok")

average = sum(scores.values()) / len(scores)
middle = responses[len(responses) / 2]
