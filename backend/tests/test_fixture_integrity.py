from fixture_cases import FIXTURE_CASES


def test_fixture_catalog_folders_exist(fixture_image_paths):
    for case in FIXTURE_CASES:
        assert fixture_image_paths(case.folder)
