Provide a concise summary of the most recent set of tool calls. The purpose of this summary is to enable another AI agent to effectively take over the current task by understanding the outcomes of these recent actions and the immediate next step, without needing to reinterpret the entire tool interaction history.

Adhere strictly to the following format. If multiple tools were called in parallel in the last step, list each action and its corresponding observation sequentially before providing a single, consolidated "NEXT_STEP":

**FORMAT**:

**ACTION**: [Clearly describe the first tool that was called and the parameters used.]
**OBSERVATION**: [Explain the result of the first tool call. Analyze how this result helps or does not help in progressing the current task.]

**NEXT_STEP**: [Based on the combined observations from all recent tool calls, clearly state what the next immediate step should be. This could be:

- Concluding the task by providing the final answer if all necessary information has now been gathered.
- Calling another specific tool (or tools, if parallel execution is again appropriate) and what information you expect to get.]
