from core.id_generator import IdGenerator

class FakeRepo:
    def __init__(self):
        self.rows = {
            ("items", "prod"): {"prefix": "ITEM_", "width": 6, "next_value": 1},
            ("prices", "prod"): {"prefix": "PRICE_", "width": 6, "next_value": 10},
        }

    def get_id_sequence(self, key: str, env: str):
        return self.rows.get((key, env))

    def upsert_id_sequence(self, key: str, env: str, next_value: int, updated_at: str, updated_by: str):
        self.rows[(key, env)]["next_value"] = next_value

repo = FakeRepo()
gen = IdGenerator(repo, env="prod")

print(gen.next_id("items", actor_user_id="U001"))
print(gen.next_id("items", actor_user_id="U001"))
print(gen.next_id("prices", actor_user_id="U001"))
