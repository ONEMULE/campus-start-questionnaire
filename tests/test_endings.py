import json
from pathlib import Path
import pytest
from backend.engine import calculate,validate_answers,AnswerError
from tests.helpers import make_answers
PATHS=json.loads((Path(__file__).with_name("ending_paths.json")).read_text("utf-8"))
@pytest.mark.parametrize("ending",list(PATHS))
def test_all_twelve_endings_have_valid_playable_paths(ending):
    answers=validate_answers(PATHS[ending],complete=True)
    assert len(answers)==32
    assert calculate(answers)["ending"]==ending

def test_malformed_clip_structure_is_validation_error():
    a=make_answers();a["N19"]={"task":"clips","order":[{},1,2,3]}
    with pytest.raises(AnswerError):validate_answers(a,complete=True)
