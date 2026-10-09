# Coding test cases and pass rate

Sandbox: **bwrap** (`app/coding/sandbox.py`). Target `cerebras/gpt-oss-120b` (temperature 0, reasoning "low", max 2048 tokens), the settings of the final benchmark run. Test generator: the same model (`app/coding/testgen.py`), every test validated on the CodeAlpaca reference. Stage A/B are frozen at `final-for-test`.

## 1. Scope

| split | coding items | Python | of which tested | reference suspect | untestable |
|---|---|---|---|---|---|
| test | 98 | 47 | 29 | 4 | 14 |
| benchmark | 10 | 5 | 2 | 1 | 2 |

Other languages on test (not run): sql 14, javascript 12, java 7, ? 6, cpp 5, html 2, csharp 2, css 2, bash 1.

Tested items: 24 function items (118 validated asserts, 2-6 per item) and 7 script items (output must equal the reference's).

## 2. Pass rate (pass@1)

`strict` = passes calling the function by the name the tests use; `lenient` = also counts answers that pass once the tests' name is bound to the answer's single top-level function (naming-only failures).

| split | variant | n | pass@1 strict | pass@1 lenient | pass | naming-only | wrong | error | ambiguous | no function | no Python |
|---|---|---|---|---|---|---|---|---|---|---|---|
| test | degraded | 29 | **6/29 (20.7%)** | 11/29 (37.9%) | 6 | 5 | 9 | 0 | 5 | 2 | 2 |
| test | stage_b | 29 | **10/29 (34.5%)** | 12/29 (41.4%) | 10 | 2 | 13 | 0 | 1 | 3 | 0 |
| benchmark | degraded | 2 | **1/2 (50.0%)** | 1/2 (50.0%) | 1 | 0 | 1 | 0 | 0 | 0 | 0 |
| benchmark | stage_b | 2 | **0/2 (0.0%)** | 1/2 (50.0%) | 0 | 1 | 1 | 0 | 0 | 0 | 0 |

Test: answers cut off at the 2048-token limit (it includes the model's hidden reasoning; the same limit as the benchmark run): degraded 2 (codealpaca-61 -> ambiguous, codealpaca-16808 -> ambiguous); stage_b 1 (codealpaca-61 -> wrong).

Test, paired (strict): both pass 6, only Stage B passes 4, only degraded passes 0, neither 19.

### Failures: naming-only vs real (test)

`real` = wrong + error + no function + no Python; `undetermined` = ambiguous (several functions under other names; not guessed).

| variant | failures (strict) | naming-only | undetermined | real |
|---|---|---|---|---|
| degraded | 23 | 5 | 5 | 13 |
| stage_b | 19 | 2 | 1 | 16 |

## 3. Per item

| split | item | mode | tests | degraded | Stage B | instruction |
|---|---|---|---|---|---|---|
| test | codealpaca-673 | function | 5 | ambiguous (0/5) | wrong (0/5), as `fib_upto_n` | Create a Python program to generate the Fibonacci series between 0 and |
| test | codealpaca-61 | function | 3 | ambiguous (0/3) | wrong (0/3) | Write a code to convert a given spredsheet in csv format to json forma |
| test | codealpaca-15999 | stdout | 1 | pass (1/1) | pass (1/1) | Output an array of even numbers from 0 to 20 using a for loop in Pytho |
| test | codealpaca-13405 | function | 5 | wrong (3/5) | pass (5/5) | update the function to return the length of 5 |
| test | codealpaca-10888 | function | 5 | pass (5/5) | pass (5/5) | Create a function that takes in two strings and returns the number of  |
| test | codealpaca-13464 | stdout | 1 | pass (1/1) | pass (1/1) | Edit the following code to print true if the condition is met, false i |
| test | codealpaca-3939 | stdout | 1 | wrong (0/1) | wrong (0/1) | Debug the following code so it can print the corresponding JSON data c |
| test | codealpaca-10863 | function | 5 | pass (5/5) | pass (5/5) | Generate a Python program to generate the square of a number. |
| test | codealpaca-16451 | stdout | 1 | pass (1/1) | pass (1/1) | Create a for loop in Python for the range between 0 and 10. |
| test | codealpaca-3141 | function | 5 | no Python (0/5) | wrong (4/5), as `random_string` | Generate a random 10-character string with an even distribution of low |
| test | codealpaca-10261 | function | 6 | wrong (5/6), as `most_frequent` | wrong (5/6), as `most_frequent` | Implement a function to return the element that appears most frequentl |
| test | codealpaca-13119 | function | 3 | wrong (2/3) | wrong (2/3) | Create a program that implements an autocomplete or predictive search  |
| test | codealpaca-13554 | function | 5 | wrong (2/5) | wrong (2/5) | Create a generator to produce "hello world" ten times |
| test | codealpaca-13669 | function | 4 | no function (0/4) | pass (4/4) | Write an algorithm to check if a number is even or not without using m |
| test | codealpaca-14051 | stdout | 1 | pass (1/1) | pass (1/1) | Rewrite the following expression using an if-else statement. |
| test | codealpaca-14085 | function | 2 | no function (0/2) | no function (0/2) | Write a code block to return a random value from a given list |
| test | codealpaca-14554 | function | 6 | ambiguous (0/6) | wrong (5/6) | Find a way to calculate the power of a number without using * or ** |
| test | codealpaca-15667 | function | 5 | naming-only (5/5), as `power` | no function (0/5) | Generate a code to find the power of n to m. |
| test | codealpaca-1596 | stdout | 1 | wrong (0/1) | wrong (0/1) | Write a script that prints out the first 100 prime numbers. |
| test | codealpaca-16808 | function | 5 | ambiguous (0/5) | no function (0/5) | Create an algorithm that computes the sum of its maximum K (given) dig |
| test | codealpaca-19215 | function | 6 | ambiguous (0/6) | wrong (0/6) | How to compare two lists in Python? |
| test | codealpaca-19529 | function | 6 | wrong (2/6), as `bubble_sort` | wrong (2/6), as `bubble_sort` | Construct a bubblesort algorithm in Python. |
| test | codealpaca-2663 | function | 5 | wrong (1/5), as `remove_greater_than` | ambiguous (0/5) | Given a linked list, remove all elements from it which have greater va |
| test | codealpaca-3277 | function | 5 | no Python (0/5) | naming-only (5/5), as `filter_greater` | Using the given array, create a function that returns a new array that |
| test | codealpaca-3526 | function | 5 | wrong (0/5), as `print_fibonacci_upto` | wrong (1/5), as `print_fibonacci_upto` | Implement a function to print the Fibonacci series up to the nth term. |
| test | codealpaca-4815 | function | 6 | naming-only (6/6), as `permute` | pass (6/6) | Generate all possible permutations of the characters in a given string |
| test | codealpaca-5398 | function | 5 | naming-only (5/5), as `min_window` | pass (5/5) | Write a function to detect the smallest window in a string containing  |
| test | codealpaca-7039 | function | 5 | naming-only (5/5), as `shuffle` | wrong (4/5), as `shuffle_list` | Create a function in Python that shuffles the elements of an input lis |
| test | codealpaca-8424 | function | 5 | naming-only (5/5), as `max_in_array` | naming-only (5/5), as `largest_number` | Utilize Python to implement an algorithm which finds the largest numbe |
| benchmark | codealpaca-2818 | stdout | 1 | wrong (0/1) | wrong (0/1) | Write a Python program to compare two strings and return True if both  |
| benchmark | codealpaca-3140 | function | 6 | pass (6/6) | naming-only (6/6), as `caesar_cipher` | Write a basic encryption function using Caesar Cipher. |

## 4. Reference suspects (kept and reported, not dropped)

| split | item | reason | instruction |
|---|---|---|---|
| test | codealpaca-6239 | reference fails on its own: NameError: name 'app' is not defined | Generate a Delete API endpoint in Python Flask for a user to delete th |
| test | codealpaca-2618 | no generated test passes on the reference | Implement a function to delete a node in a linked list |
| test | codealpaca-174 | a Python task whose reference does not parse as Python | Design a function in Python to delete duplicates from a list. |
| test | codealpaca-19346 | a Python task whose reference does not parse as Python | How would you check if a list of integers contains only even numbers? |
| benchmark | codealpaca-5135 | reference fails on its own: FileNotFoundError: [Errno 2] No such file or directory: 'employees.xml' | Parse the following XML code and print all the "name" fields. |

## 5. Untestable Python items

| split | item | reason |
|---|---|---|
| test | codealpaca-18707 | no function and no printed output (a value or fragment) |
| test | codealpaca-13745 | no function and no printed output (a value or fragment) |
| test | codealpaca-11465 | no function and no printed output (a value or fragment) |
| test | codealpaca-7029 | interactive: the reference reads input() |
| test | codealpaca-12679 | no function and no printed output (a value or fragment) |
| test | codealpaca-13417 | no function and no printed output (a value or fragment) |
| test | codealpaca-18616 | no function and no printed output (a value or fragment) |
| test | codealpaca-16116 | no function and no printed output (a value or fragment) |
| test | codealpaca-12944 | needs packages outside the standard library: requests |
| test | codealpaca-14863 | no function and no printed output (a value or fragment) |
| test | codealpaca-2453 | no function and no printed output (a value or fragment) |
| test | codealpaca-3865 | no function and no printed output (a value or fragment) |
| test | codealpaca-5339 | needs packages outside the standard library: sklearn |
| test | codealpaca-6014 | needs packages outside the standard library: pandas |
| benchmark | codealpaca-1569 | output depends on the clock or randomness (datetime) |
| benchmark | codealpaca-13667 | interactive: the reference reads input() |
