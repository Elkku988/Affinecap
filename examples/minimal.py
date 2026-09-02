"""The entire affinecap lifecycle in a few lines."""

from affinecap import CapabilityConsumedError, issue

publish = issue(lambda: "published", label="review passed")
print(publish.consume(lambda action: action()))

try:
    publish.consume(lambda action: action())
except CapabilityConsumedError:
    print("already used")
