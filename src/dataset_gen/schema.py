from dataclasses import dataclass
from typing import List, Literal, Optional

Difficulty = Literal["easy", "medium", "hard"]
ExampleType = Literal["qa", "rewrite", "critique"]


@dataclass
class DatasetExample:
  """Schema de um exemplo sintético gerado a partir do NASA SE Handbook."""

  id: str
  instruction: str
  response: str
  difficulty: Difficulty
  example_type: ExampleType
  section_title: str
  section_path: str  # ex.: "3.2.1 Technical Requirements"
  source_chunks: List[str]
  tags: List[str]
  notes: Optional[str] = None

