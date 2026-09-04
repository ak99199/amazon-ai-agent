"""Narrow storage contracts and composition for Ads control-plane state."""
from typing import Protocol


class AdsControlPlaneRepository(Protocol):
    def get_decision(self,seller_id,marketplace_id,profile_id,recommendation_id): ...
    def save_decision(self,decision): ...
    def list_execution_plans(self,seller_id,marketplace_id,profile_id,limit=50): ...
    def save_execution_plan(self,plan): ...
    def get_write_intent(self,seller_id,marketplace_id,profile_id,write_intent_id): ...
    def save_write_intent(self,intent): ...
    def transition_write_intent(self,seller_id,marketplace_id,profile_id,write_intent_id,new_status,event_type,created_at): ...
    def save_sealed_write_command(self,command): ...
    def list_sealed_write_commands(self,seller_id,marketplace_id,profile_id,status=None,limit=50): ...


CONTROL_PLANE_METHODS=frozenset({
    "get_decision","list_decisions","save_decision","list_decision_events",
    "get_execution_plan","list_execution_plans","save_execution_plan","list_execution_events",
    "list_rule_versions","get_rule_version","get_active_rule_version","create_rule_version",
    "update_rule_version_status","activate_rule_version","rollback_rule_version","get_rollback_candidate",
    "insert_rule_activation_event","list_rule_activation_events","get_latest_rule_activation_event",
    "list_rule_tuning_proposals","get_rule_tuning_proposal","save_rule_tuning_proposal",
    "review_rule_tuning_proposal",
    "save_write_intent","get_write_intent","list_write_intents","list_write_intent_events",
    "transition_write_intent","save_sealed_write_command","list_sealed_write_commands",
    "list_sealed_write_command_events"})


class AdsRepositoryCapabilities:
    """Routes control-plane calls explicitly while preserving historical APIs."""
    def __init__(self,historical,control_plane):self.historical=historical;self.control_plane=control_plane
    def __getattr__(self,name):
        return getattr(self.control_plane if name in CONTROL_PLANE_METHODS else self.historical,name)
