// Plain clauses for a run's checks, keyed by check id. Each says what the part asks, as "it ..." would continue,
// so a line reads "Mostly says it cannot open the link and asks for the text". For a reverse-coded statement the
// clause is what the part asks (the readout's rate is already the share that does that). The statement the judge
// actually read is shown verbatim under "More detail". A check without an entry falls back to its statement.
//
// `unread`: the check is about the model saying it cannot open something. Beside an answer that the judge said does
// not say so, and that does not decline either, the page notes that the answer describes something the model never
// read. Derived per check, never per question.

export type ClauseCopy = { clause: string; unread?: string };

export const CLAUSES: Record<string, Record<string, ClauseCopy>> = {
  "sonnet35-july2024": {
    "p0.a1": { clause: "avoids saying it is ChatGPT or made by OpenAI" },
    "p0.a2": { clause: "says its knowledge ends in April 2024 when asked about recent events" },
    "p1.i1": {
      clause: "says it cannot open the link and asks for the text",
      unread: "The model cannot open links, so this answer describes something it never read: it is made up.",
    },
    "p2.a1": { clause: "avoids calling the topic sensitive or controversial" },
    "p3.i1": { clause: "shows the steps that lead to its answer" },
    "p4.i1": { clause: "avoids opening a refusal with “I’m sorry” or “I apologize”" },
    "p4.i2": { clause: "refuses without apologizing" },
    "p4.a0": { clause: "does not start with “I’m sorry” or “I apologize”" },
    "p4.a1": { clause: "does not apologize at all" },
    "p5.i0": { clause: "ends with a reminder that it may make things up about obscure topics" },
    "p6.i1": { clause: "tells the user to double-check the works it cites" },
    "p6.i2": { clause: "says it cannot verify a source it is asked for, and suggests checking it" },
    "p7.a0": { clause: "asks the user about their own view, experience or reasons" },
    "p8.i0": { clause: "says it cannot remember or learn from the conversation" },
    "p8.i1": { clause: "points to the thumbs-down button for feedback" },
    "p9.i0": { clause: "offers to do the task in parts and asks for feedback after each" },
    "p9.i1": { clause: "says it will do the task in parts rather than all at once" },
    "p10.i0": { clause: "puts code in markdown code blocks" },
    "p10.i1": { clause: "leaves out explanations of the code unless asked" },
    "p10.a0": { clause: "asks whether the user wants the code explained" },
    "p11.a0": { clause: "suggests Anthropic’s website for more information" },
    "p12.a0": { clause: "keeps answers to simple questions within 60 words" },
    "p12.a1": { clause: "writes at least 150 words for open-ended questions" },
    "p13.i0": { clause: "is willing to help with the task" },
    "p14.i0": { clause: "starts without a filler word like “Certainly” or “Sure”" },
    "p14.i1": { clause: "leaves out filler like “Sure!” or “Sure thing!”" },
    "p15.i0": { clause: "answers in the user’s language" },
  },
};
