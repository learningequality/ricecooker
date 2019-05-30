Kolibri Content Channel Rubric
==============================




Issue tracker
-------------
Every content channel on the Kolibri platform undergoes a rigorous review process
in order to ensure content structure, metadata, and functionality is set appropriately.

In order to help with this process, we use the "Issue tracker" table to report
problems so that people responsible for creating the channel can address them.

Issue tracker columns:
  - `Issue ID`: internal numeric identifier (or `github:nn` for issues two-way-synced with the chef's github repo)
  - `Type` (multi select): what type of issue is this (see full list of options below)
  - `Severity` (Blocker || Nice to have): how bad is the issue
  - `URL`: A link to studio, a demoserver, or the source website where issue is visible
  - `Screenshots` (files): screenshot that shows the issue in action
  - `Issue description` (text): provide detailed description of what the issue is, how to reproduce, and any additional info (e.g. copy-paste of errors from the JavaScript console)
  - `Possible fixes` (text): provide suggestions (technical or not) for how issue could be fixes or worked around
  - `Assigned to` (notion user): track the person that is supposed to fix this issue
  - `Status` (Not started||In progress||Fixes): track progress on issue fix
  - `Created`: record the date when the issues was added
  - `Created by`: record who filed the issue

Issue types:
  - `Missing content`: some content from the source was not imported
  - `Structure`: problem with the channel structure
  - `Title`: problem with titles, e.g. titles that are too long or not informative
  - `Description`: use to flag description problems (non-informative or repeating junk text)
  - `Metadata`: problem with metadata associated with nodes (language, licensing info, author, role visibility, tags)
  - `Thumbnails`: flag broken or missing thumbnails on the channel, topics, or content nodes
  - `Display issue`:  the content doesn't look right (HTML/CSS issues) or doesn't work as expected (JavaScript issues)
  - `Learning UX`: any problem that might interfere with learning user experience
  - `Video compression`: if videos are not compressed enough (files too large) of too compressed (cannot read text)
  - `Bulk corrections`: flag issues that are might require bulk metadata edits on numerous content nodes
  - `Translation`: content files or metadata are partially or completely in the wrong language
  - `Enhancement`: use to keep of possible enhancements or additions that could be made to improve coach or learner experience


Issue severity:
 - `Blocker`: this issue must be fixed before the channel can go into QA
 - `Nice to have`: non-blocking issues like corrections, enhancements, and minor learning UX problems


