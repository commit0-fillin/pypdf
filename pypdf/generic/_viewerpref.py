from typing import Any, List, Optional
from ._base import BooleanObject, NameObject, NumberObject
from ._data_structures import ArrayObject, DictionaryObject
f_obj = BooleanObject(False)

class ViewerPreferences(DictionaryObject):

    def __new__(cls: Any, value: Any=None) -> 'ViewerPreferences':

        def _add_prop_bool(key: str, deft: Optional[BooleanObject]) -> property:
            return property(lambda self: self._get_bool(key, deft), lambda self, v: self._set_bool(key, v), None, f'\n            Returns/Modify the status of {key}, Returns {deft} if not defined\n            ')

        def _add_prop_name(key: str, lst: List[str], deft: Optional[NameObject]) -> property:
            return property(lambda self: self._get_name(key, deft), lambda self, v: self._set_name(key, lst, v), None, f'\n            Returns/Modify the status of {key}, Returns {deft} if not defined.\n            Acceptable values: {lst}\n            ')

        def _add_prop_arr(key: str, deft: Optional[ArrayObject]) -> property:
            return property(lambda self: self._get_arr(key, deft), lambda self, v: self._set_arr(key, v), None, f'\n            Returns/Modify the status of {key}, Returns {deft} if not defined\n            ')

        def _add_prop_int(key: str, deft: Optional[int]) -> property:
            return property(lambda self: self._get_int(key, deft), lambda self, v: self._set_int(key, v), None, f'\n            Returns/Modify the status of {key}, Returns {deft} if not defined\n            ')
        cls.hide_toolbar = _add_prop_bool('/HideToolbar', f_obj)
        cls.hide_menubar = _add_prop_bool('/HideMenubar', f_obj)
        cls.hide_windowui = _add_prop_bool('/HideWindowUI', f_obj)
        cls.fit_window = _add_prop_bool('/FitWindow', f_obj)
        cls.center_window = _add_prop_bool('/CenterWindow', f_obj)
        cls.display_doctitle = _add_prop_bool('/DisplayDocTitle', f_obj)
        cls.non_fullscreen_pagemode = _add_prop_name('/NonFullScreenPageMode', ['/UseNone', '/UseOutlines', '/UseThumbs', '/UseOC'], NameObject('/UseNone'))
        cls.direction = _add_prop_name('/Direction', ['/L2R', '/R2L'], NameObject('/L2R'))
        cls.view_area = _add_prop_name('/ViewArea', [], None)
        cls.view_clip = _add_prop_name('/ViewClip', [], None)
        cls.print_area = _add_prop_name('/PrintArea', [], None)
        cls.print_clip = _add_prop_name('/PrintClip', [], None)
        cls.print_scaling = _add_prop_name('/PrintScaling', [], None)
        cls.duplex = _add_prop_name('/Duplex', ['/Simplex', '/DuplexFlipShortEdge', '/DuplexFlipLongEdge'], None)
        cls.pick_tray_by_pdfsize = _add_prop_bool('/PickTrayByPDFSize', None)
        cls.print_pagerange = _add_prop_arr('/PrintPageRange', None)
        cls.num_copies = _add_prop_int('/NumCopies', None)
        cls.enforce = _add_prop_arr('/Enforce', ArrayObject())
        return DictionaryObject.__new__(cls)

    def __init__(self, obj: Optional[DictionaryObject]=None) -> None:
        super().__init__()
        if obj is not None:
            self.update(obj.items())
        self.indirect_reference = getattr(obj, 'indirect_reference', None)
