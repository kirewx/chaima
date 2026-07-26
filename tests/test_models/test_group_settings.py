from chaima.models.group import Group


def test_group_show_sds_research_links_defaults_true():
    group = Group(name="Lab")
    assert group.show_sds_research_links is True
