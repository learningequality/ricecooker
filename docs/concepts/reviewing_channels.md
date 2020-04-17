Reviewing Kolibri content channels
==================================
Every content channel on the Kolibri platform benefits from a the review process
that ensures the content structure, metadata, and functionality is up to standard.
This is broadly referred to as "channel review," "providing feedback," or "QA."
Everyone on the LE team is a potential channel reviewer, and external partners
can also be asked to review channels when they have capacity.



Issue tracker
-------------
Channel reviewers can use the "Issue tracker" table to report problems so that
developers responsible for creating the channel can address them.

### Issue tracker columns
  - `Issue ID`: internal numeric identifier
    (or `github:nn` for two-way-synced issues with the chef's github repo)
  - `Type` (multi select): what type of issue is this (see full list of options below)
  - `Severity` (Blocker || Nice to have): how bad is the issue
  - `URL`: A link to studio, a demo server, or the source website where the issue is visible
  - `Screenshots` (files): screenshot that shows the issue in action
  - `Issue description` (text): provide detailed description of what the issue is, how to reproduce, and any additional info (e.g. copy-paste of errors from the JavaScript console)
  - `Possible fixes` (text): provide suggestions (technical or not) for how issue could be fixed and ideas for workarounds
  - `Assigned to` (notion user): track the person that is supposed to fix this issue
  - `Status` (Not started||In progress||Fixed): track progress on issue fix
  - `Created`: record the date when the issue was added
  - `Created by`: record who filed the issue

#### Issue types
  - `Missing content`: some content from the source was not imported
  - `Structure`: problem with the channel structure
  - `Title`: problem with titles, e.g. titles that are too long or not informative
  - `Description`: use to flag description problems (non-informative or repeating junk text)
  - `Metadata`: problem with metadata associated with nodes (language, licensing info, author, role visibility, tags)
  - `Thumbnails`: flag broken or missing thumbnails on the channel, topics, or content nodes
  - `Display issue`:  the content doesn't look right (HTML/CSS issues) or doesn't work as expected (JavaScript issues)
  - `Learning UX`: any problem that might interfere with learning user experience
  - `Video compression`: if videos are not compressed enough (files too large)
    or alternatively too compressed (cannot read text)
  - `Bulk corrections`: flag issues that might require bulk metadata edits on numerous content nodes
  - `Translation`: content files or metadata are partially or completely in the wrong language
  - `Enhancement`: use to keep track of possible enhancements or additions that could be made to improve coach or learner experience


#### Issue severity
  - `Blocker`: this issue must be fixed before the channel can go into QA
  - `Nice to have`: non-blocking issues like corrections, enhancements,
    and minor learning UX problems



Who can be a channel reviewer?
------------------------------
You can. Whenever you need a distraction, take 20 minutes and place yourself in
the learner's shoes and go explore the channel on the demo server link provided
on the notion card.  If you notice any issues  while browsing, add them to the
Issue tracker table. That's it. Learn something today.

