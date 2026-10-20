# Aliasing, a function call and an error: what does each line do?
prompt_parts = ["You are a helpful assistant."]
history = prompt_parts          # NOT a copy: both names point at one list
history.append("User: hi")


def average_length(chunks):
    total = 0
    for chunk in chunks:
        total += len(chunk)
    return total / len(chunks)


print(len(prompt_parts))
avg = average_length(history)
print(f"avg = {avg:.1f}")
empty = []
print(average_length(empty))
