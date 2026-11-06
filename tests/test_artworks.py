import pytest
def test_get_seeded_artwork(client, seeded_db):
    # Arrange: seeded_db has already loaded the 11 artworks (the Mona Lisa is first)
    expected = {"id": 1, **seeded_db[0]}

    # Act
    response = client.get("/artworks/1")

    # Assert
    assert response.status_code == 200
    assert response.json() == expected

def test_list_artworks_empty(client):
    expected = []

    response = client.get("/artworks/")

    assert response.status_code == 200
    assert response.json() == expected

def test_create_artwork(client, sample_artwork ):
    response = client.post("/artworks/", json=sample_artwork)
    
    assert response.status_code == 201
    
    response_data = response.json()

    assert "id" in response_data
    assert isinstance(response_data["id"], int)
    
    expected_response = {"id": response_data["id"], **sample_artwork}
    assert response_data == expected_response

def test_create_artwork_is_saved(client, created_artwork):
    artwork_id = created_artwork["id"]

    response = client.get(f"/artworks/{artwork_id}")

    assert response.status_code == 200
    assert response.json() == created_artwork

def test_update_artwork(client, created_artwork, updated_artwork):
    artwork_id = created_artwork["id"]

    expected = {"id": artwork_id, **updated_artwork}

    response = client.put(f"/artworks/{artwork_id}", json=updated_artwork)

    assert response.status_code == 200
    assert response.json() == expected

    get_response = client.get(f"/artworks/{artwork_id}")
    assert get_response.status_code == 200
    assert get_response.json() == expected

def test_delete_artwork(client, created_artwork):
    artwork_id = created_artwork["id"]

    response = client.delete(f"/artworks/{artwork_id}")

    assert response.status_code == 204
    assert response.content == b""

    get_respose = client.get(f"/artworks/{artwork_id}")
    assert get_respose.status_code == 404

# Unhappy-Path Tests
@pytest.mark.parametrize(
    "method, use_body",
    [
        ("get", False),
        ("put", True),
        ("delete", False),
    ],
    ids=["get", "put", "delete"],
)
def test_artwork_not_found(client, sample_artwork, method, use_body):
    kwargs = {"json": sample_artwork} if use_body else {}
    response = client.request(method, "/artworks/9999", **kwargs)

    assert response.status_code == 404
    assert response.json() == {"detail": "Artwork not found"}

def test_no_integer_id(client):
    response = client.get("/artworks/mona-lisa")

    assert response.status_code == 422

def test_create_duplicate(client, created_artwork, sample_artwork):
    response = client.post("/artworks/", json=sample_artwork)

    assert response.status_code == 409
    assert response.json() == {"detail": "An artwork with that title and artist already exists"}

def test_create_duplicate_ignores_case(client, created_artwork, sample_artwork):
    sample_artwork["title"] = sample_artwork["title"].upper()
    sample_artwork["artist"] = sample_artwork["artist"].lower()

    response = client.post("/artworks/", json=sample_artwork)

    assert response.status_code == 409

def test_update_into_duplicate(client, seeded_db):
    mona_lisa = seeded_db[0]
    duplicate_payload = {
        "title": mona_lisa["title"],
        "artist": mona_lisa["artist"],
        "year": 1489,
        "medium": "Oil on walnut panel",
        "museum": "Czartoryski Museum",
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/b/bf/Lady_with_an_Ermine_-_Leonardo_da_Vinci_%28adjusted_levels%29.jpg"
    }
    response = client.put("/artworks/2", json=duplicate_payload)
    assert response.status_code == 409 

    get_response = client.get("/artworks/2")
    assert get_response.status_code == 200

def test_update_same_title_and_artist_is_allowed(client, created_artwork):
    artwork_id = created_artwork["id"]
    updated_payload = {
        "title": created_artwork["title"],
        "artist": created_artwork["artist"],
        "year": created_artwork["year"],
        "medium": created_artwork["medium"],
        "museum": "The Louvre Museum", 
        "image_url": created_artwork["image_url"]
    }
    
    response = client.put(f"/artworks/{artwork_id}", json=updated_payload)
    assert response.status_code == 200

# Paramerization
@pytest.mark.parametrize(
    "missing_field",
    [
        "title", 
        "artist", 
        "year", 
        "medium", 
        "museum", 
        "image_url"
    ],
    ids=["missing-title", "missing-artist", "missing-year", "missing-medium", "missing-museum", "missing-image_url"],       
)
def test_create_missing_field(client, sample_artwork, missing_field):
    payload = sample_artwork
    payload.pop(missing_field)

    response = client.post("/artworks/", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", missing_field]

@pytest.mark.parametrize(
    "invalid_values",
    [
        {"year": 3000},
        {"year": "nineteen-oh-seven"},
        {"title": ""},
    ],
    ids=["future-year", "year-not-int", "empty-title"]
)
def test_create_invalid_value(client, sample_artwork, invalid_values):
    payload = sample_artwork.copy()
    payload.update(invalid_values)

    response = client.post("/artworks/", json=payload)

    assert response.status_code == 422

@pytest.mark.parametrize(
    "params, expected_counts",
    [
        ({"limit": 3}, 3),
        ({"limit": 0}, 0),
        ({"skip": 10, "limit": 5}, 1),
        ({"skip": 20, "limit": 5}, 0)
    ],
    ids=["limit-3", "limit-0", "skip-10-limit-5", "skip-past-end"],
)

def test_pagination_counts(client, seeded_db, params, expected_counts):
    response = client.get("/artworks/", params=params)

    assert response.status_code == 200
    assert len(response.json()) == expected_counts

@pytest.mark.parametrize(
    "params",
    [
        {"skip": -1},       
        {"limit": 500},    
    ],
    ids=["negative-skip", "excessive-limit"],
)

def test_pagination_invalid(client, seeded_db, params):
    response = client.get("/artworks/", params=params)

    assert response.status_code == 422

@pytest.mark.parametrize(
    "artist_query, expected_titles",
    [
        ("Claude Monet", ["Impression, Sunrise", "Woman with a Parasol – Madame Monet and Her Son"]), 
        ("monet", ["Impression, Sunrise", "Woman with a Parasol – Madame Monet and Her Son"]),        
        ("Leonardo da Vinci", ["Mona Lisa", "Lady with an Ermine"]),
        ("Random", []),                                            
    ],
    ids=["full-name", "lowercase-partial", "another-full-name", "no-match"],
)

def test_filter_by_artist(client, seeded_db, artist_query, expected_titles):
    response = client.get("/artworks/", params={"artist": artist_query})

    assert response.status_code == 200 

    data = response.json()
    titles = [artwork["title"] for artwork in data]

    assert titles == expected_titles