from io import StringIO, BytesIO
import csv

from chaima.models.chemical import Chemical
from chaima.models.container import Container
from chaima.models.storage import StorageLocation
from chaima.models.supplier import Supplier
from chaima.services import export as export_service


async def test_export_csv_one_row_per_container(session, group, user):
    loc = StorageLocation(name="Shelf A", kind="shelf")
    session.add(loc)
    sup = Supplier(name="Sigma", group_id=group.id)
    session.add(sup)
    chem = Chemical(name="Ethanol", cas="64-17-5", group_id=group.id, created_by=user.id)
    session.add(chem)
    await session.flush()
    session.add(Container(
        chemical_id=chem.id, location_id=loc.id, supplier_id=sup.id,
        created_by=user.id, identifier="E-001", amount=1.0, unit="L",
        ordered_by_name="M. Schmidt",
    ))
    session.add(Container(
        chemical_id=chem.id, location_id=loc.id,
        created_by=user.id, identifier="E-002", amount=0.5, unit="L",
    ))
    await session.commit()

    data = await export_service.export_chemicals(session, group.id, filters={}, fmt="csv")
    reader = csv.reader(StringIO(data.decode("utf-8")))
    rows = list(reader)
    header = rows[0]
    body = rows[1:]

    assert header[:7] == ["name", "cas", "smiles", "location", "identifier", "quantity", "unit"]
    assert len(body) == 2
    e001 = next(r for r in body if r[4] == "E-001")
    assert e001[0] == "Ethanol"
    assert e001[1] == "64-17-5"
    assert e001[3] == "Shelf A"
    assert e001[5] == "1.0"
    assert e001[6] == "L"
    assert "M. Schmidt" in e001  # ordered_by column
    assert "Sigma" in e001        # supplier column


async def test_export_includes_chemical_without_containers(session, group, user):
    chem = Chemical(name="Isolated", group_id=group.id, created_by=user.id)
    session.add(chem)
    await session.commit()

    data = await export_service.export_chemicals(session, group.id, filters={}, fmt="csv")
    reader = csv.reader(StringIO(data.decode("utf-8")))
    rows = list(reader)
    body = rows[1:]
    assert len(body) == 1
    assert body[0][0] == "Isolated"
    assert body[0][4] == ""  # identifier empty
    assert body[0][5] == ""  # quantity empty
