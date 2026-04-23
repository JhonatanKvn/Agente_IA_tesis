class EvaluationResult:
    def __init__(self):
        self.score = 0
        self.max_score = 5
        self.feedback = "Evaluación no implementada"
        self.code_transcription = ""
        self.strengths = []
        self.improvements = []
        self.rubric_breakdown = []

def evaluate_with_ocr_space(*args, **kwargs):
    return EvaluationResult()

# trigger redeploy
