# Phase 4: Retrieval Evaluation & Error Analysis

This project includes a runnable retrieval-evaluation harness:

```bash
python scripts/evaluate_rag.py --project-id demo-project --retrieval-only
```

It reads the cases from:

- [evaluation_cases.sample.json](/C:/Users/Fady2/Downloads/NLP2/NLP-project/docs/evaluation_cases.sample.json)

and writes the generated report to:

- [phase4_evaluation_report.md](/C:/Users/Fady2/Downloads/NLP2/NLP-project/docs/phase4_evaluation_report.md)

For direct probing of multi-chunk and out-of-scope behavior, the project also includes:

```bash
python -m scripts.phase4_probe
```

## Three Real Edge Cases From The Academic Rules PDF

### 1. Minimum GPA for graduation
- Query: `ما الحد الأدنى للمعدل التراكمي المطلوب للتخرج؟`
- Failure pattern: retrieval often ranks a grading-scale table above the chunk that explicitly states the minimum cumulative GPA for graduation.
- Why the architecture missed: the PDF mixes narrative policy text with dense tables, so semantic similarity overweights nearby grading vocabulary and underweights the exact graduation sentence.

### 2. Exceeding the maximum study period
- Query: `ماذا يحدث إذا لم يحقق الطالب شروط التخرج خلال الحد الأقصى للدراسة؟`
- Failure pattern: retrieval can surface general grading or warning text instead of the dismissal rule tied to the maximum allowed study duration.
- Why the architecture missed: this rule lives near other academic-status clauses, and the sentence-window chunker can produce neighboring chunks with overlapping academic terms but different intent.

### 3. Attendance threshold for entering the exam
- Query: `ما هي نسبة حضور الطالب المطلوبة لدخول الامتحان؟`
- Failure pattern: the correct attendance chunk is present, but top-1 retrieval may prefer exam-mark distribution or other exam-related policy text.
- Why the architecture missed: the query shares tokens with multiple exam-policy chunks, while the exact attendance consequence appears deeper in the page and is diluted by surrounding administrative text.

## What This Phase Proves

1. The system can now be evaluated with repeatable, file-specific edge cases instead of ad hoc manual testing.
2. Retrieval accuracy is measured not only by source file name, but also by whether the retrieved chunk contains the expected evidence phrase.
3. The current weak spots are ranking errors inside the same document, not stale mixed-document pollution as before.

## Manual Probe Notes

### Multi-chunk graduation question
- Query: `ما شروط التخرج من حيث عدد الساعات والمعدل التراكمي والتدريب الصيفي؟`
- Retrieved pages after the fixes: `5, 2, 6, 3, 3`
- Observation: retrieval clearly spans multiple chunks and pages, not one chunk. The context includes graduation hours, GPA-related graduation policy, and summer training requirements.
- Note: when the live provider was rate-limited, the probe fell back to retrieval-only mode, so the run proves multi-chunk retrieval coverage but not final generation quality.

### Out-of-scope housing question
- Query: `ما رسوم السكن الجامعي لطلاب الكلية؟`
- Retrieved pages after the fixes: `none`
- Observation: after the retrieval fixes, the system returns an empty retrieval set instead of pulling loose academic-policy chunks from the same PDF.
- Note: this confirms the generic out-of-scope rejection logic is now working for this case.

## Arabic vs English Probe

### Same multi-chunk question in Arabic and English
- Arabic query: `ما شروط التخرج من حيث عدد الساعات والمعدل التراكمي والتدريب الصيفي؟`
- Retrieved pages after the fixes: `5, 2, 6, 3, 3`
- English query: `What are the graduation requirements in terms of credit hours, GPA, and summer training?`
- Retrieved pages after the fixes: `2, 3, 9, 12, 10`
- Observation: both languages now retrieve non-empty context from the same corpus. Arabic retrieval stays closer to the policy pages, while English retrieval still reaches further into curriculum-table pages because the document itself is Arabic and OCR-heavy.

### Same out-of-scope question in Arabic and English
- Arabic query: `ما رسوم السكن الجامعي لطلاب الكلية؟`
- English query: `What are the dormitory housing fees for students?`
- Observation: both now return `0` retrieved chunks and fall back to `I don't know`, which confirms the out-of-scope rejection fix works in both languages.
