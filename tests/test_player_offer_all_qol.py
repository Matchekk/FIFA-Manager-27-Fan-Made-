import importlib.util
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "offer_all", ROOT / "tools/install-player-offer-all-qol.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PlayerOfferAllQolTests(unittest.TestCase):
    def test_transform_reuses_native_button_style_and_slot(self):
        xml = b'''<Screen><Trfm>
          <Obj Rtti="TextButton" Uid="BtAccept"><Meta/><Appearance Rect="1,2,3,4"/>
            <TexInactive><Texture Resrc="art\\button.tga"/></TexInactive>
            <ColText String="$OLD"/></Obj>
          <Obj Rtti="TextButton" Visible="false" Uid="BtPlayerDetails">
            <Appearance Rect="0,0,1,1"/><ColText/></Obj>
        </Trfm></Screen>'''
        output = MODULE.transform_screen(xml)
        MODULE.validate_screen(output, dark=False)
        root = MODULE.ET.fromstring(output)
        accept = next(n for n in root.iter("Obj") if n.get("Uid") == "BtAccept")
        offer_all = next(n for n in root.iter("Obj") if n.get("Uid") == "BtPlayerDetails")
        self.assertEqual(accept.find("Appearance").get("Rect"), "1,2,3,4")
        self.assertEqual(offer_all.find("Appearance").get("Rect"), "703,795,503,32")
        self.assertEqual(offer_all.find("ColText").get("String"), "Spieler allen Vereinen anbieten")

    def test_legacy_translation_has_all_seven_columns_for_cleanup(self):
        self.assertEqual(len(MODULE.TRANSLATION.split("|")), 7)

    def test_packaged_plugin_is_x86_and_contains_result_text(self):
        path = ROOT / "data/qol/player-offer-all/plugins/FM27.PlayerOfferAll.asi"
        payload = path.read_bytes()
        pe_offset = struct.unpack_from("<I", payload, 0x3C)[0]
        self.assertEqual(struct.unpack_from("<H", payload, pe_offset + 4)[0], 0x14C)
        self.assertIn(b"IDS_OTC_INTRESTED", payload)
        self.assertNotIn(b"MessageBoxW", payload)


if __name__ == "__main__":
    unittest.main()
