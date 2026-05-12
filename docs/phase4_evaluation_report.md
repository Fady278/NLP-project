# Phase 4: Retrieval Evaluation & Error Analysis

- Project ID: `demo-project`
- Cases run: **3**
- Retrieval hit rate: **3/3**
- Evidence-backed hit rate: **2/3**
- Full-pass rate: **0/3**

## Case Summary

| Case | Retrieval | Evidence | Answer | Status | Failure Reason |
| --- | --- | --- | --- | --- | --- |
| `edge-1-graduation-gpa` | hit | hit | IDK | fail | relevant context found but answer abstained |
| `edge-2-maximum-study-period` | hit | hit | IDK | fail | relevant context found but answer abstained |
| `edge-3-attendance-threshold` | hit | miss | IDK | fail | wrong chunk retrieved |

## Edge Cases

### edge-1-graduation-gpa
- Query: `ما الحد الأدنى للمعدل التراكمي المطلوب للتخرج؟`
- Failure type: **relevant context found but answer abstained**
- Retrieved count: 1
- Top source: `C:\Users\Fady2\Downloads\NLP2\NLP-project\data\raw\uploads\6b6bef75_FCIS-ASU_قواعد لائحة الساعات المعتمدة.pdf`
- Evidence hit: yes
- Notes: The correct GPA rule exists in the corpus, but a noisy grading table chunk can outrank it.
- Answer excerpt: `I don't know.`

### edge-2-maximum-study-period
- Query: `ماذا يحدث إذا لم يحقق الطالب شروط التخرج خلال الحد الأقصى للدراسة؟`
- Failure type: **relevant context found but answer abstained**
- Retrieved count: 1
- Top source: `C:\Users\Fady2\Downloads\NLP2\NLP-project\data\raw\uploads\6b6bef75_FCIS-ASU_قواعد لائحة الساعات المعتمدة.pdf`
- Evidence hit: yes
- Notes: The relevant dismissal rule is present, but retrieval tends to rank nearby grading-policy chunks first.
- Answer excerpt: `I don't know.`

### edge-3-attendance-threshold
- Query: `ما هي نسبة حضور الطالب المطلوبة لدخول الامتحان؟`
- Failure type: **wrong chunk retrieved**
- Retrieved count: 1
- Top source: `C:\Users\Fady2\Downloads\NLP2\NLP-project\data\raw\uploads\6b6bef75_FCIS-ASU_قواعد لائحة الساعات المعتمدة.pdf`
- Evidence hit: no
- Notes: The attendance rule exists, but exam and grading text from adjacent chunks can dominate the ranking.
- Answer excerpt: `I don't know.`
