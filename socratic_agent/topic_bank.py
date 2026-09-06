"""
Curated content for the prototype's topic catalog: introductory Python
concepts spanning Beginner to Intermediate difficulty, sourced from
w3schools.com/python's own tutorial ordering (Variables -> Data Types ->
If...Else -> Loops -> Lists -> Functions), so the pilot can be tried by
students at different levels rather than only on one fixed topic.

Each Topic bundles its own learning objectives and misconception bank —
the small, hand-curated grounding reference the Diagnostic agent uses to
*actively* test for known misconceptions rather than only reacting to
whatever the student happens to say (Section 2.9.1's response to the
"perception-guidance asymmetry" gap). This stays intentionally small and
hand-curated, not a retrieved knowledge base, consistent with the proposal's
lightweight, prompt-only scope (Section 3.2).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LearningObjective:
    id: str
    statement: str
    seed_question: str  # the Wonder-stage opener the Facilitator can start from
    canonical_answer: str  # what "the answer" is, told to agents so they can self-check for leaking it
    protected_literals: tuple[str, ...]  # literal strings that, if an agent says them, count as a leak


@dataclass(frozen=True)
class Misconception:
    id: str
    label: str
    description: str
    counterexample_hint: str  # a concrete case the Diagnostician can use to surface it


@dataclass(frozen=True)
class Topic:
    id: str
    name: str
    emoji: str
    difficulty: str  # "Beginner" | "Intermediate"
    description: str
    learning_objectives: tuple[LearningObjective, ...]
    misconceptions: tuple[Misconception, ...]


# ---------------------------------------------------------------------------------
# Topic: Variables & Data Types (Beginner)
# ---------------------------------------------------------------------------------
_VARIABLES = Topic(
    id="variables",
    name="Variables & Data Types",
    emoji="🧮",
    difficulty="Beginner",
    description="How names are bound to values, and Python's dynamic typing.",
    learning_objectives=(
        LearningObjective(
            id="VO1",
            statement="Understand that assigning one variable from another copies the value at that moment, for simple types.",
            seed_question=(
                "Here's a snippet:\n```python\nx = 5\ny = x\nx = 10\nprint(y)\n```\n"
                "Before running it in your head — what do you think this prints, and why?"
            ),
            canonical_answer=(
                "It prints 5 — y was assigned the value of x (5) at that moment; reassigning x "
                "afterward doesn't change y, since y holds its own independent value."
            ),
            protected_literals=("prints 5", "y is 5", "y = 5", "5, not 10"),
        ),
        LearningObjective(
            id="VO2",
            statement="Understand Python's dynamic typing: a variable's type is determined by its current value and can change on reassignment.",
            seed_question=(
                "```python\nx = 5\nx = \"hello\"\n```\n"
                "What is the type of x after these two lines, and is this allowed in Python?"
            ),
            canonical_answer=(
                "x is now a string (type str) — Python is dynamically typed, so a variable can be "
                "reassigned to a value of a different type, and this is completely allowed."
            ),
            protected_literals=("x is a string", "type str", "str type", "now a string"),
        ),
    ),
    misconceptions=(
        Misconception(
            id="VAR_M1_SAME_REFERENCE",
            label="Thinks reassigning one variable changes another",
            description="Believes `y = x` creates a permanent link so changing x later also changes y.",
            counterexample_hint="Ask them to trace `x = 5; y = x; x = 10; print(y)` step by step.",
        ),
        Misconception(
            id="VAR_M2_STATIC_TYPE",
            label="Assumes variable types are fixed",
            description="Believes a variable's type is locked once assigned, and reassigning to a different type is an error.",
            counterexample_hint="Ask what happens if you reassign a variable holding a number to a string.",
        ),
        Misconception(
            id="VAR_M3_QUOTES_CONFUSION",
            label="Confuses literal text with variable names",
            description="Thinks `print(x)` prints the literal text \"x\" rather than its value, or forgets quotes are needed for string literals.",
            counterexample_hint="Ask them to predict the output of `x = \"hi\"; print(x)` versus `print(\"x\")`.",
        ),
        Misconception(
            id="VAR_M4_INT_STRING_CONCAT",
            label="Assumes numbers and strings concatenate directly",
            description="Believes `\"Age: \" + 25` works without converting the number to a string first.",
            counterexample_hint="Ask them to predict what happens when you add a string and a number with +.",
        ),
    ),
)

# ---------------------------------------------------------------------------------
# Topic: Conditionals (If...Else) (Beginner)
# ---------------------------------------------------------------------------------
_CONDITIONALS = Topic(
    id="conditionals",
    name="Conditionals (If / Elif / Else)",
    emoji="🔀",
    difficulty="Beginner",
    description="How Python picks exactly one branch of an if/elif/else chain.",
    learning_objectives=(
        LearningObjective(
            id="CO1",
            statement="Understand that only the first true branch of an if/elif/else chain runs, evaluated top to bottom.",
            seed_question=(
                "```python\nx = 15\nif x > 10:\n    print(\"A\")\nelif x > 5:\n    print(\"B\")\nelse:\n    print(\"C\")\n```\n"
                "What prints here, and why don't the other branches also run?"
            ),
            canonical_answer=(
                "It prints A — Python checks conditions top-to-bottom and runs only the first branch "
                "whose condition is true, then skips the rest of the chain, even though x > 5 is also true."
            ),
            protected_literals=("prints A", "only A"),
        ),
        LearningObjective(
            id="CO2",
            statement="Understand that a chained comparison like `5 < x < 10` checks both bounds at once.",
            seed_question=(
                "```python\nx = 7\nprint(5 < x < 10)\n```\nWhat does this print, and what is Python actually checking?"
            ),
            canonical_answer=(
                "It prints True — Python evaluates the chained comparison as (5 < x) AND (x < 10) "
                "together, so it's checking whether x lies strictly between 5 and 10."
            ),
            protected_literals=("prints True", "evaluates to True"),
        ),
    ),
    misconceptions=(
        Misconception(
            id="COND_M1_ALL_TRUE_RUN",
            label="Thinks every true branch executes",
            description="Believes all branches whose condition is true will run, not just the first matching one.",
            counterexample_hint="Ask them to trace an if/elif chain where two conditions would both be true.",
        ),
        Misconception(
            id="COND_M2_ASSIGN_VS_COMPARE",
            label="Confuses = with ==",
            description="Confuses assignment (=) with comparison (==) inside a condition.",
            counterexample_hint="Ask what `if x = 5:` does versus `if x == 5:`.",
        ),
        Misconception(
            id="COND_M3_TRUTHY_CONFUSION",
            label="Doesn't understand truthy/falsy values",
            description="Thinks `if 0:` or `if \"\":` behaves the same as `if True:`.",
            counterexample_hint="Ask them to predict whether `if 0:` or `if \"\":` runs their body.",
        ),
        Misconception(
            id="COND_M4_ELSE_NEEDS_CONDITION",
            label="Thinks else needs its own condition",
            description="Believes `else` requires a condition, or that `elif` and `else` are interchangeable.",
            counterexample_hint="Ask them what condition, if any, `else` checks.",
        ),
    ),
)

# ---------------------------------------------------------------------------------
# Topic: Loops (for / while) (Intermediate)
# ---------------------------------------------------------------------------------
_LOOPS = Topic(
    id="loops",
    name="Loops (for / while)",
    emoji="🔁",
    difficulty="Intermediate",
    description="How for/while loops execute, loop-variable scope, and off-by-one pitfalls.",
    learning_objectives=(
        LearningObjective(
            id="LO1",
            statement="Explain the step-by-step execution order of a loop (condition check, body, update, recheck).",
            seed_question=(
                "Here's a snippet:\n"
                "```python\n"
                "i = 0\n"
                "while i < 3:\n"
                "    print(i)\n"
                "    i += 1\n"
                "```\n"
                "Before you run it in your head line by line — what do you think this will print, and why?"
            ),
            canonical_answer=(
                "It prints 0, then 1, then 2 (three lines), because the condition `i < 3` is "
                "checked before each iteration and becomes false once i reaches 3."
            ),
            protected_literals=("0, 1, 2", "0,1,2", "0 1 2", "0\n1\n2"),
        ),
        LearningObjective(
            id="LO2",
            statement="Correctly reason about the loop variable's value/scope after the loop terminates.",
            seed_question=(
                "Suppose that same loop finishes running. What do you think the value of `i` is "
                "right after the loop ends, and is `i` still usable at all at that point?"
            ),
            canonical_answer=(
                "After the loop, i is 3, and it is still accessible afterward, because Python "
                "loop variables are not block-scoped to the loop body."
            ),
            protected_literals=("i is 3", "i equals 3", "i will be 3", "value of i is 3"),
        ),
        LearningObjective(
            id="LO3",
            statement="Avoid off-by-one errors when iterating over a range or sequence of known length.",
            seed_question=(
                "If you wanted to print the numbers 1 through 5 using `range(...)`, what would you "
                "write inside `range(...)`, and why does that give you exactly those five numbers?"
            ),
            canonical_answer=(
                "range(1, 6) — the stop value must be one past the last number you want, so "
                "range(1, 6) yields 1, 2, 3, 4, 5."
            ),
            protected_literals=("range(1, 6)", "range(1,6)"),
        ),
    ),
    misconceptions=(
        Misconception(
            id="LOOP_M1_OFF_BY_ONE",
            label="Off-by-one in range bounds",
            description="Believes range(n) includes n, or range(a, b) includes b.",
            counterexample_hint="Ask them to trace `list(range(1, 5))` by hand and count the items.",
        ),
        Misconception(
            id="LOOP_M2_VAR_VANISHES",
            label="Loop variable 'disappears' after the loop",
            description="Believes the loop variable is out of scope or reset once the loop ends.",
            counterexample_hint="Ask what `print(i)` would output immediately after the loop, before assuming an error.",
        ),
        Misconception(
            id="LOOP_M3_CHECK_ORDER",
            label="Wrong execution order",
            description="Believes the update happens before the body, or the condition is only checked once at the start.",
            counterexample_hint="Ask them to trace the loop turn-by-turn: check condition, run body, then update.",
        ),
        Misconception(
            id="LOOP_M4_INFINITE_LOOP_BLIND",
            label="Doesn't notice a missing update can loop forever",
            description="Doesn't connect a missing/incorrect update statement to non-termination.",
            counterexample_hint="Present a while-loop missing `i += 1` and ask what happens when it runs.",
        ),
        Misconception(
            id="LOOP_M5_FOR_WHILE_CONFUSION",
            label="Conflates for-loops and while-loops",
            description="Assumes a `for` loop needs a manual counter increment, or that `while` auto-iterates over a sequence.",
            counterexample_hint="Ask them to rewrite a `for i in range(5)` loop as a `while` loop and note what they must add.",
        ),
        Misconception(
            id="LOOP_M6_BODY_RUNS_ONCE",
            label="Thinks the body runs only once per 'pass' regardless of condition",
            description="Treats the loop body as executing a single time and the loop keyword as just a label.",
            counterexample_hint="Ask how many times `print(i)` actually executes, and to list each printed value.",
        ),
    ),
)

# ---------------------------------------------------------------------------------
# Topic: Lists (Intermediate)
# ---------------------------------------------------------------------------------
_LISTS = Topic(
    id="lists",
    name="Lists",
    emoji="📋",
    difficulty="Intermediate",
    description="Zero-based indexing, negative indices, and list mutability/aliasing.",
    learning_objectives=(
        LearningObjective(
            id="LI1",
            statement="Understand zero-based indexing and negative indices.",
            seed_question=(
                "```python\nfruits = [\"apple\", \"banana\", \"cherry\"]\nprint(fruits[1])\nprint(fruits[-1])\n```\n"
                "What do these two lines print, and why?"
            ),
            canonical_answer=(
                "fruits[1] prints 'banana' (indexing starts at 0, so index 1 is the second item), "
                "and fruits[-1] prints 'cherry' (negative indices count from the end, so -1 is the last item)."
            ),
            protected_literals=(
                "fruits[1] prints 'banana'", "fruits[1] is 'banana'",
                "fruits[-1] prints 'cherry'", "fruits[-1] is 'cherry'",
            ),
        ),
        LearningObjective(
            id="LI2",
            statement="Understand that assigning a list to another variable aliases the same list object, unlike simple values.",
            seed_question=(
                "```python\na = [1, 2, 3]\nb = a\nb.append(4)\nprint(a)\n```\n"
                "What does this print, and why might that be surprising compared to plain numbers?"
            ),
            canonical_answer=(
                "It prints [1, 2, 3, 4] — `b = a` doesn't copy the list, it makes b point to the SAME "
                "list object as a, so modifying b through .append() also changes what a shows."
            ),
            protected_literals=("[1, 2, 3, 4]", "prints [1, 2, 3, 4]"),
        ),
    ),
    misconceptions=(
        Misconception(
            id="LIST_M1_INDEX_STARTS_AT_1",
            label="Assumes indexing starts at 1",
            description="Believes the first element of a list is at index 1, not 0.",
            counterexample_hint="Ask which index accesses the very first item of a list.",
        ),
        Misconception(
            id="LIST_M2_NEGATIVE_INDEX_CONFUSION",
            label="Doesn't understand negative indices",
            description="Doesn't know that negative indices count backward from the end of the list.",
            counterexample_hint="Ask what `my_list[-1]` refers to.",
        ),
        Misconception(
            id="LIST_M3_COPY_ASSUMPTION",
            label="Believes list assignment copies the list",
            description="Believes `b = a` creates an independent copy of a list rather than an alias to the same object.",
            counterexample_hint="Ask them to trace `a = [1,2]; b = a; b.append(3); print(a)`.",
        ),
        Misconception(
            id="LIST_M4_INDEX_OUT_OF_RANGE_BLIND",
            label="Doesn't expect an out-of-range index to error",
            description="Believes accessing an index beyond the list's length returns None or wraps around instead of raising an error.",
            counterexample_hint="Ask what happens if you access index 10 on a 3-item list.",
        ),
    ),
)

# ---------------------------------------------------------------------------------
# Topic: Functions (Intermediate)
# ---------------------------------------------------------------------------------
_FUNCTIONS = Topic(
    id="functions",
    name="Functions",
    emoji="🧩",
    difficulty="Intermediate",
    description="Local scope/parameters, and the difference between printing and returning.",
    learning_objectives=(
        LearningObjective(
            id="FN1",
            statement="Understand that a function's parameter is a local variable that doesn't affect the caller's original variable (for simple types).",
            seed_question=(
                "```python\ndef add_one(x):\n    x = x + 1\n    return x\n\nn = 5\nresult = add_one(n)\nprint(n)\nprint(result)\n```\n"
                "What do these two print lines show, and why doesn't n change?"
            ),
            canonical_answer=(
                "print(n) prints 5 and print(result) prints 6 — inside the function, x is a local "
                "variable that starts as a copy of n's value; modifying x inside the function doesn't "
                "affect the original n outside it."
            ),
            protected_literals=("n) prints 5", "result) prints 6", "prints 5 and 6", "5 and then 6"),
        ),
        LearningObjective(
            id="FN2",
            statement="Understand that a function without an explicit return statement returns None.",
            seed_question=(
                "```python\ndef greet(name):\n    print(\"Hello, \" + name)\n\nresult = greet(\"Sam\")\nprint(result)\n```\n"
                "What does the final print(result) show, and why?"
            ),
            canonical_answer=(
                "It prints None — greet() prints a message but never uses a return statement, so "
                "calling it gives back None by default, which is what gets stored in result."
            ),
            protected_literals=("prints None", "result is None"),
        ),
    ),
    misconceptions=(
        Misconception(
            id="FUNC_M1_MUTATES_CALLER",
            label="Thinks a function changes the caller's variable",
            description="Believes changing a parameter inside a function changes the caller's original variable, for simple types.",
            counterexample_hint="Ask them to trace `n = 5; add_one(n); print(n)`.",
        ),
        Misconception(
            id="FUNC_M2_PRINT_IS_RETURN",
            label="Confuses printing with returning",
            description="Believes `result = greet(\"Sam\")` captures whatever the function printed.",
            counterexample_hint="Ask what value `result` actually holds after calling a function that only prints.",
        ),
        Misconception(
            id="FUNC_M3_MISSING_RETURN_ERROR",
            label="Thinks a missing return is an error",
            description="Believes a function without a return statement is a syntax error rather than implicitly returning None.",
            counterexample_hint="Ask what happens when you call a function that has no return statement at all.",
        ),
        Misconception(
            id="FUNC_M4_PARAM_NAME_MATTERS",
            label="Thinks argument names must match parameter names",
            description="Believes the variable name used at the call site must match the function's parameter name.",
            counterexample_hint="Ask them to call a function with an argument variable named differently from the parameter.",
        ),
    ),
)

TOPICS: tuple[Topic, ...] = (_VARIABLES, _CONDITIONALS, _LOOPS, _LISTS, _FUNCTIONS)


def _validate_protected_literals() -> None:
    """Fails fast at import time if any protected_literal would false-positive against
    its own seed code — the exact bug class hit when CO1's literal '"A"' collided with
    the literal `print("A")` in the seed snippet (a faithful restatement of the code
    then looked like a leak). Every new topic/objective gets this check for free."""
    import re

    def norm(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip().lower()

    for topic in TOPICS:
        for objective in topic.learning_objectives:
            seed_norm = norm(objective.seed_question)
            for literal in objective.protected_literals:
                if norm(literal) in seed_norm:
                    raise AssertionError(
                        f"{topic.id}/{objective.id}: protected_literal {literal!r} appears "
                        f"verbatim in its own seed_question — it will false-positive the "
                        f"leak guard the moment the Facilitator quotes the code back. "
                        f"Use a more specific, answer-revealing phrase instead."
                    )


_validate_protected_literals()

_TOPIC_BY_ID = {t.id: t for t in TOPICS}


def get_topic(topic_id: str) -> Topic | None:
    return _TOPIC_BY_ID.get(topic_id)


def objective_by_index(topic: Topic, index: int) -> LearningObjective | None:
    if 0 <= index < len(topic.learning_objectives):
        return topic.learning_objectives[index]
    return None


def misconceptions_summary(topic: Topic) -> str:
    return "\n".join(
        f"- {m.id} ({m.label}): {m.description} Probe idea: {m.counterexample_hint}"
        for m in topic.misconceptions
    )


_MISCONCEPTION_BY_ID_GLOBAL = {m.id: m for t in TOPICS for m in t.misconceptions}


def misconception_label(misconception_id: str) -> str:
    """Human-readable label for a misconception id, for display in the UI/dashboard.

    Ids are prefixed per topic (e.g. LOOP_, VAR_, COND_, LIST_, FUNC_) so this lookup
    works globally without needing the originating topic, which keeps the teacher
    dashboard's cross-topic aggregate view simple.
    """
    m = _MISCONCEPTION_BY_ID_GLOBAL.get(misconception_id)
    return m.label if m else misconception_id
