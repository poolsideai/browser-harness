# Dialogs

Native dialogs such as alerts, confirms, prompts, and beforeunload prompts can
pause the page's JavaScript thread. If `page_info()` returns a `dialog` object,
handle or dismiss the dialog before continuing normal verification.

Do not record a walkthrough through a dialog unless the dialog itself is the
behavior being demonstrated. Resolve surprise dialogs, verify the clean state
with a screenshot, then re-record.
