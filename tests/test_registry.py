from eval import registry


def test_load_registry_returns_non_empty_list():
    docs = registry.load_registry()
    assert isinstance(docs, list)
    assert docs, "registry must declare at least one document"
    assert all("document_id" in d for d in docs)


def test_registered_document_ids_contains_loss_run_fixture():
    ids = registry.registered_document_ids()
    assert "loss_run_libertymutual" in ids


def test_find_document_returns_entry_and_none():
    entry = registry.find_document("loss_run_libertymutual")
    assert entry is not None
    assert entry.get("doc_type") == "loss_run"

    assert registry.find_document("no_such_document") is None


def test_doc_type_for_known_and_unknown():
    assert registry.doc_type_for("loss_run_libertymutual") == "loss_run"
    assert registry.doc_type_for("no_such_document") is None


def test_golden_path_returns_existing_file_or_none():
    path = registry.golden_path_for("loss_run_libertymutual")
    # Either the golden file ships with the repo or it doesn't; the contract
    # is "return an existing Path or None", never a broken path.
    assert path is None or path.is_file()
