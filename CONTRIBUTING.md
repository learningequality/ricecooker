Contributing
============

Contributions to this project are welcome and are in fact greatly appreciated!
Every little bit helps and credit will always be given. Whether you're a junior
Python programmer looking for a open source project to contribute to, an advanced
programmer that can help us make `ricecooker` more efficient, we'd love to hear
from you. We've outlined below some of the ways you can contribute.


Types of Contributions
----------------------

### Cheffing

Use your Python and ricecooker knowledge to help with the content integration of content sources that will benefit offline learners from around the world.


### Report Bugs

Report bugs at [https://github.com/learningequality/ricecooker/issues](https://github.com/learningequality/ricecooker/issues)

If you are reporting a bug, please include:

* Which version of `ricecooker` you're using.
* Which operating system you're using (name and version).
* Any details about your local setup that might be helpful in troubleshooting.
* Detailed steps to reproduce the bug.


### Submit Feedback

The best way to send us your feedback is to file an issue at
[https://github.com/learningequality/ricecooker/issues](https://github.com/learningequality/ricecooker/issues).

If you are proposing a new feature:

* Explain in detail how it would work.
* Try to keep the scope as narrow as possible to make it easier to implement.
* Remember this is a volunteer-driven project, and contributions are welcome :)

### Code contributions

The `ricecooker` project is open for code, testing, and documentation contributions. The `ricecooker.utils` package is constantly growing with new helper methods that simplify various aspects of the content extraction, transformations, and upload to Studio.

First, visit [Contributing to our open code base](https://learningequality.org/contributing-to-our-open-code-base/) where you will find general contributing guidelines and how to find an issue to work on.

Becoming a ricecooker developer
-------------------------------

Ready to contribute? In order to work on the `ricecooker` code you'll first need
to have [Python 3.9+](https://www.python.org/downloads/) on your computer.

Here are the steps for setting up `ricecooker` for local development:

1. Fork the `ricecooker` repo on GitHub.
   The result will be your very own copy repository for the ricecooker
   codebase `https://github.com/<your-github-username>/ricecooker`.
2. Clone your fork of the repository locally, and go into the `ricecooker` directory:

    ```
    git clone git@github.com:<your-github-username>/ricecooker.git
    cd ricecooker/
    ```

3. Install [uv](https://docs.astral.sh/uv/getting-started/installation/) if you don't have it already:

    ```
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

    On Windows:
    ```
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

4. Install the `ricecooker` code and its dependencies:

    ```
    uv sync --group dev
    ```

5. Create a branch for local development:

    ```
    git checkout -b name-of-your-bugfix-or-feature
    ```

   Now you can make your changes locally.


6. When you're done making changes, check that your changes pass linting
   and the `ricecooker` test suite:

   Run linting:
    ```
    uvx prek run --all-files
    ```

   Run the tests:
    ```
    uv run --group test pytest
    ```

   Run tests across all supported Python versions:
    ```
    make test-all
    ```


7. Commit your changes and push your branch to GitHub:

    ```
    git add .
    git commit -m "A detailed description of your changes."
    git push origin name-of-your-bugfix-or-feature
    ```


8. Open a pull request through the GitHub web interface.




Pull Request Guidelines
-----------------------

Before you submit a pull request, check that it meets these guidelines:

1. The pull request should include tests.
2. If the pull request adds functionality, the docs should be updated. Put
   your new functionality into a function with a docstring, and add the
   feature to the list in `README.md`.
3. The pull request should work for Python 3.9+. Check the GitHub Actions CI
   and make sure that the tests pass for all supported Python versions.





Developer Tips
--------------

To run a subset of tests, you can specify a particular module name:

```
$ py.test tests.test_licenses
```
