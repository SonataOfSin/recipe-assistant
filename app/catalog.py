"""Small built-in recipe catalog used to make a fresh local install usable."""

from copy import deepcopy


def _recipe(
    title: str,
    cuisine: str,
    meal_type: str,
    minutes: int,
    tags: list[str],
    ingredients: list[tuple[str, float, str]],
    steps: list[str],
    description: str,
) -> dict:
    # Convert compact ingredient tuples into the same shape used by the API.
    return {
        "title": title,
        "description": description,
        "cuisine": cuisine,
        "meal_type": meal_type,
        "servings": 2,
        "total_time_min": minutes,
        "diet_tags": tags,
        "ingredients": [
            {"name": name, "quantity": quantity, "unit": unit}
            for name, quantity, unit in ingredients
        ],
        "steps": steps,
        "source": "catalog",
    }


RECIPES = [
    # Starter recipes keep first-run search useful before users add their own.
    _recipe("Lemon Chicken and Rice", "Mediterranean", "dinner", 35, ["gluten_free", "dairy_free"], [("chicken", 300, "g"), ("rice", 150, "g"), ("lemon", 1, "pcs"), ("olive oil", 1, "tbsp"), ("salt", 1, "tsp")], ["Cook rice according to its package directions.", "Pan-sear the chicken until fully cooked, then finish with lemon.", "Serve the chicken over rice."], "A bright, simple chicken dinner served with fluffy rice."),
    _recipe("Tomato Chickpea Stew", "Mediterranean", "dinner", 30, ["vegan", "vegetarian", "gluten_free", "dairy_free"], [("chickpeas", 400, "g"), ("tomatoes", 300, "g"), ("onion", 1, "pcs"), ("olive oil", 1, "tbsp"), ("cumin", 1, "tsp")], ["Soften the onion in olive oil.", "Add tomatoes, chickpeas, and cumin; simmer for 20 minutes.", "Season and serve."], "A hearty pantry-friendly chickpea and tomato stew."),
    _recipe("Spinach Mushroom Pasta", "Italian", "dinner", 25, ["vegetarian"], [("pasta", 200, "g"), ("mushrooms", 150, "g"), ("spinach", 100, "g"), ("cream", 100, "ml"), ("garlic", 1, "clove")], ["Boil pasta until just tender.", "Saute mushrooms and garlic, then stir in spinach and cream.", "Toss with drained pasta."], "Creamy pasta with mushrooms and fresh spinach."),
    _recipe("Avocado Tomato Toast", "International", "breakfast", 10, ["vegan", "vegetarian", "dairy_free"], [("bread", 2, "slices"), ("avocado", 1, "pcs"), ("tomatoes", 1, "pcs"), ("lemon", 0.5, "pcs")], ["Toast the bread.", "Mash avocado with lemon.", "Spread on toast and top with tomato."], "Quick avocado toast with fresh tomato."),
    _recipe("Greek Yogurt Berry Bowl", "Greek", "breakfast", 5, ["vegetarian", "gluten_free"], [("Greek yogurt", 200, "g"), ("berries", 100, "g"), ("honey", 1, "tbsp"), ("walnuts", 15, "g")], ["Spoon yogurt into a bowl.", "Top with berries, honey, and walnuts."], "A cool yogurt bowl with fruit and a little crunch."),
    _recipe("Red Lentil Soup", "Middle Eastern", "lunch", 35, ["vegan", "vegetarian", "gluten_free", "dairy_free"], [("red lentils", 180, "g"), ("carrot", 1, "pcs"), ("onion", 1, "pcs"), ("vegetable broth", 700, "ml"), ("cumin", 1, "tsp")], ["Soften onion and carrot.", "Add lentils, broth, and cumin.", "Simmer until soft and blend if desired."], "A warming, naturally vegan lentil soup."),
    _recipe("Cheese and Spinach Omelet", "French", "breakfast", 12, ["vegetarian", "gluten_free"], [("egg", 3, "pcs"), ("spinach", 50, "g"), ("cheese", 30, "g"), ("butter", 1, "tsp")], ["Whisk eggs.", "Wilt spinach in butter, pour in eggs, and cook gently.", "Add cheese, fold, and serve."], "A quick omelet filled with spinach and cheese."),
    _recipe("Roasted Vegetable Quinoa", "International", "lunch", 40, ["vegan", "vegetarian", "gluten_free", "dairy_free"], [("quinoa", 150, "g"), ("zucchini", 1, "pcs"), ("bell pepper", 1, "pcs"), ("chickpeas", 200, "g"), ("olive oil", 1, "tbsp")], ["Roast chopped vegetables and chickpeas with oil.", "Cook quinoa until fluffy.", "Combine and season."], "A colorful bowl of roasted vegetables, chickpeas, and quinoa."),
    _recipe("Peanut Noodle Salad", "Asian", "lunch", 20, ["vegan", "vegetarian", "dairy_free"], [("rice noodles", 180, "g"), ("peanut butter", 2, "tbsp"), ("soy sauce", 1, "tbsp"), ("carrot", 1, "pcs"), ("lime", 1, "pcs")], ["Cook noodles and rinse cool.", "Whisk peanut butter, soy sauce, and lime.", "Toss noodles with sauce and sliced carrot."], "A tangy noodle salad with a creamy peanut dressing."),
    _recipe("Baked Salmon and Broccoli", "Mediterranean", "dinner", 25, ["gluten_free", "dairy_free"], [("salmon", 250, "g"), ("broccoli", 200, "g"), ("lemon", 1, "pcs"), ("olive oil", 1, "tbsp")], ["Heat oven to 200 C.", "Arrange salmon and broccoli on a tray; season and add lemon.", "Bake until salmon is cooked through."], "A simple tray-baked salmon dinner with broccoli."),
    _recipe("Georgian Lobio", "Georgian", "dinner", 50, ["vegan", "vegetarian", "gluten_free", "dairy_free"], [("kidney beans", 400, "g"), ("onion", 1, "pcs"), ("walnuts", 30, "g"), ("cilantro", 15, "g"), ("garlic", 1, "clove")], ["Soften the onion.", "Mash beans lightly and warm with garlic.", "Fold in ground walnuts and cilantro."], "A home-style Georgian bean dish with walnuts and herbs."),
    _recipe("Chicken Vegetable Stir-Fry", "Asian", "dinner", 25, ["dairy_free"], [("chicken", 250, "g"), ("bell pepper", 1, "pcs"), ("broccoli", 150, "g"), ("soy sauce", 1, "tbsp"), ("rice", 120, "g")], ["Cook rice.", "Stir-fry chicken until fully cooked.", "Add vegetables and soy sauce; cook until crisp-tender."], "A quick chicken and vegetable stir-fry served with rice."),
    _recipe("Banana Oat Pancakes", "American", "breakfast", 20, ["vegetarian"], [("oats", 100, "g"), ("banana", 1, "pcs"), ("egg", 1, "pcs"), ("milk", 100, "ml"), ("butter", 1, "tsp")], ["Mash banana and mix with oats, egg, and milk.", "Cook small pancakes in a buttered pan.", "Serve warm."], "Soft banana pancakes for a relaxed breakfast."),
    _recipe("Cucumber Tomato Salad", "Georgian", "lunch", 12, ["vegan", "vegetarian", "gluten_free", "dairy_free"], [("cucumber", 1, "pcs"), ("tomatoes", 2, "pcs"), ("cilantro", 10, "g"), ("olive oil", 1, "tbsp"), ("walnuts", 20, "g")], ["Chop cucumber and tomatoes.", "Crush walnuts and mix with herbs and oil.", "Dress the salad and serve."], "A crisp Georgian-inspired salad with a walnut dressing."),
    _recipe("Mushroom Barley Pilaf", "Eastern European", "dinner", 40, ["vegetarian"], [("barley", 150, "g"), ("mushrooms", 200, "g"), ("onion", 1, "pcs"), ("vegetable broth", 450, "ml"), ("butter", 1, "tbsp")], ["Rinse barley.", "Saute onion and mushrooms in butter.", "Add barley and broth; simmer until tender."], "A savory mushroom pilaf with chewy barley."),
    _recipe("Sweet Potato Black Bean Tacos", "Mexican", "dinner", 35, ["vegan", "vegetarian", "gluten_free", "dairy_free"], [("sweet potato", 1, "pcs"), ("black beans", 250, "g"), ("corn tortillas", 4, "pcs"), ("lime", 1, "pcs"), ("avocado", 1, "pcs")], ["Roast diced sweet potato until tender.", "Warm black beans and tortillas.", "Fill tacos and finish with lime and avocado."], "Plant-based tacos with sweet potato and black beans."),
    _recipe("Lemon Butter Shrimp", "Mediterranean", "dinner", 18, ["gluten_free"], [("shrimp", 250, "g"), ("butter", 1, "tbsp"), ("lemon", 1, "pcs"), ("garlic", 1, "clove"), ("rice", 120, "g")], ["Cook rice.", "Saute garlic and shrimp until shrimp are opaque.", "Finish with butter and lemon."], "Fast lemon-garlic shrimp served with rice."),
    _recipe("Roasted Tomato Soup", "Italian", "lunch", 45, ["vegan", "vegetarian", "gluten_free", "dairy_free"], [("tomatoes", 500, "g"), ("onion", 1, "pcs"), ("garlic", 2, "cloves"), ("olive oil", 1, "tbsp"), ("vegetable broth", 300, "ml")], ["Roast tomatoes, onion, and garlic until soft.", "Blend with warm broth.", "Season and serve."], "A smooth soup made from sweet roasted tomatoes."),
    _recipe("Chicken Caesar Wrap", "American", "lunch", 25, [], [("chicken", 200, "g"), ("tortilla", 2, "pcs"), ("lettuce", 60, "g"), ("mayonnaise", 1, "tbsp"), ("parmesan", 20, "g")], ["Cook chicken thoroughly and slice.", "Toss lettuce with mayonnaise and parmesan.", "Wrap everything in tortillas."], "A familiar chicken and greens wrap."),
    _recipe("Apple Cinnamon Oatmeal", "International", "breakfast", 15, ["vegan", "vegetarian", "gluten_free", "dairy_free"], [("rolled oats", 100, "g"), ("apple", 1, "pcs"), ("cinnamon", 1, "tsp"), ("oat milk", 250, "ml"), ("maple syrup", 1, "tbsp")], ["Simmer oats in oat milk.", "Stir in chopped apple and cinnamon.", "Finish with maple syrup."], "A cozy bowl of oats, apple, and cinnamon."),
    _recipe("Caprese Salad", "Italian", "lunch", 10, ["vegetarian", "gluten_free"], [("tomatoes", 2, "pcs"), ("mozzarella", 125, "g"), ("basil", 10, "g"), ("olive oil", 1, "tbsp")], ["Slice tomatoes and mozzarella.", "Layer with basil.", "Drizzle with olive oil."], "A simple tomato, mozzarella, and basil salad."),
    _recipe("Lemon Herb Couscous", "North African", "lunch", 20, ["vegan", "vegetarian", "dairy_free"], [("couscous", 150, "g"), ("lemon", 1, "pcs"), ("parsley", 15, "g"), ("chickpeas", 200, "g"), ("olive oil", 1, "tbsp")], ["Prepare couscous with hot water.", "Fluff with a fork and fold in chickpeas and parsley.", "Add lemon and olive oil."], "A fresh couscous bowl with herbs and chickpeas."),
    _recipe("Beef and Pepper Skillet", "American", "dinner", 30, ["gluten_free", "dairy_free"], [("beef", 250, "g"), ("bell pepper", 2, "pcs"), ("onion", 1, "pcs"), ("rice", 150, "g"), ("soy sauce", 1, "tbsp")], ["Cook rice.", "Brown beef in a skillet.", "Add peppers, onion, and soy sauce; cook until tender."], "A one-pan beef and pepper dinner with rice."),
    _recipe("Carrot Ginger Soup", "International", "lunch", 35, ["vegan", "vegetarian", "gluten_free", "dairy_free"], [("carrot", 400, "g"), ("ginger", 10, "g"), ("onion", 1, "pcs"), ("vegetable broth", 600, "ml"), ("coconut milk", 100, "ml")], ["Soften onion and ginger.", "Add carrots and broth; simmer until soft.", "Blend smooth and stir through coconut milk."], "A smooth, gently spiced carrot soup."),
    _recipe("Tuna White Bean Salad", "Mediterranean", "lunch", 15, ["gluten_free", "dairy_free"], [("tuna", 150, "g"), ("white beans", 250, "g"), ("tomatoes", 1, "pcs"), ("lemon", 1, "pcs"), ("parsley", 10, "g")], ["Drain tuna and beans.", "Combine with chopped tomato and parsley.", "Dress with lemon."], "A filling no-cook tuna and bean salad."),
    _recipe("Vegan Chocolate Pudding", "International", "dessert", 15, ["vegan", "vegetarian", "gluten_free", "dairy_free"], [("silken tofu", 300, "g"), ("dark chocolate", 100, "g"), ("maple syrup", 2, "tbsp"), ("vanilla", 1, "tsp")], ["Melt the chocolate gently.", "Blend with tofu, maple syrup, and vanilla.", "Chill until set."], "A silky dairy-free chocolate dessert."),
    _recipe("Georgian Ajapsandali", "Georgian", "dinner", 45, ["vegan", "vegetarian", "gluten_free", "dairy_free"], [("eggplant", 1, "pcs"), ("bell pepper", 1, "pcs"), ("tomatoes", 2, "pcs"), ("onion", 1, "pcs"), ("cilantro", 15, "g")], ["Brown eggplant and set aside.", "Cook onion, pepper, and tomatoes until soft.", "Return eggplant, simmer, and finish with cilantro."], "A Georgian vegetable stew with eggplant and herbs."),
    _recipe("Egg Fried Rice", "Asian", "dinner", 20, [], [("rice", 250, "g"), ("egg", 2, "pcs"), ("peas", 80, "g"), ("carrot", 1, "pcs"), ("soy sauce", 1, "tbsp")], ["Scramble eggs and set aside.", "Stir-fry rice, peas, and carrot.", "Return eggs and season with soy sauce."], "A quick fried rice with egg and vegetables."),
    _recipe("Pear Walnut Salad", "International", "lunch", 12, ["vegetarian", "gluten_free"], [("pear", 1, "pcs"), ("arugula", 60, "g"), ("walnuts", 20, "g"), ("blue cheese", 25, "g"), ("olive oil", 1, "tbsp")], ["Arrange arugula and sliced pear.", "Top with walnuts and blue cheese.", "Dress lightly with olive oil."], "A crisp pear salad with walnuts and blue cheese."),
    _recipe("Baked Falafel Bowl", "Middle Eastern", "dinner", 40, ["vegan", "vegetarian", "dairy_free"], [("chickpeas", 250, "g"), ("parsley", 15, "g"), ("garlic", 1, "clove"), ("tahini", 1, "tbsp"), ("cucumber", 1, "pcs")], ["Pulse chickpeas with parsley and garlic; shape into balls.", "Bake until golden.", "Serve with cucumber and tahini."], "A baked falafel bowl with tahini and fresh cucumber."),
    _recipe("Blueberry Muffins", "American", "dessert", 35, ["vegetarian"], [("flour", 200, "g"), ("blueberries", 120, "g"), ("milk", 120, "ml"), ("egg", 1, "pcs"), ("butter", 50, "g")], ["Mix dry and wet ingredients separately.", "Fold together with blueberries.", "Bake at 180 C until risen and golden."], "Tender muffins filled with blueberries."),
]


def get_catalog() -> list[dict]:
    # Callers may add derived fields, so give each one independent recipe data.
    return deepcopy(RECIPES)
