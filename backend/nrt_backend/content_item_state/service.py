from nrt_backend.content_item_state.repository import ContentItemStateRepository


class ContentItemStateService:
    def __init__(self, repository=None):
        self.repository = repository or ContentItemStateRepository()

    def apply_action(self, user_id, content_item_id, action, recommendation_event_id=None):
        return self.repository.apply_action(user_id, content_item_id, action, recommendation_event_id)
