#После подключения реальных данных заменяется через factory.make_provider()
from .providers.json import JSONProvider
class DemoProvider(JSONProvider):
    def __init__(self, base_dir: str = "data/demo"):
        super().__init__( hotels_path=f"{base_dir}/hotels.json",
            offers_path=f"{base_dir}/offers.json",
            reviews_path=f"{base_dir}/reviews.json", )