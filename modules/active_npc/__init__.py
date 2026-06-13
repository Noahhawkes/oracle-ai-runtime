"""active_npc — Self-contained ORACLE-powered Active NPC Intelligence module."""
from .npc_models import *
from .npc_identity import NPCIdentity, make_identity
from .npc_memory import NPCMemory, new_memory, new_belief
from .npc_needs import NPCNeeds, default_needs
from .npc_goals import NPCGoals, make_goal
from .npc_relationships import NPCRelationships
from .npc_world_model import NPCWorldModel
from .npc_perception import NPCPerception
from .npc_reasoning import NPCReasoning
from .npc_action_policy import NPCActionPolicy, PolicyContext
from .npc_dialogue import NPCDialogue
from .npc_runtime import NPCRuntime, CycleResult
