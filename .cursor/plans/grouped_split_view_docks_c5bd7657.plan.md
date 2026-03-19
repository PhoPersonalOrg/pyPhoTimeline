---
name: Grouped split view docks
overview: Revise the split-view implementation so primary and compare tracks are wrapped into separate parent group docks. This uses the existing dock-group and nested-dock support in the docking layer instead of manually coordinating per-row resizing.
todos:
  - id: tag-primary-and-compare-docks
    content: Assign stable dock_group_names to primary and compare track docks so they can be wrapped into separate parent column groups.
    status: completed
  - id: relayout-column-groups-on-split
    content: When the split action runs, dissolve any old wrappers if needed and re-run layout_dockGroups so both columns become grouped parent docks.
    status: completed
  - id: preserve-scroll-behavior
    content: Keep the existing primary vs compare viewport sync separation intact while moving docks into grouped parent containers.
    status: completed
isProject: false
---

# Group split tracks into parent docks

## Key finding

The docking layer already supports grouped parent docks. `[DynamicDockDisplayAreaContentMixin](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\docking\dynamic_dock_display_area.py)` can collect docks by `dock_group_names`, then wrap each group into a nested parent dock with `layout_dockGroups()`.

```224:245:pypho_timeline/docking/dynamic_dock_display_area.py
def layout_dockGroups(self):
    grouped_dock_items_dict: Dict[str, List[Dock]] = self.get_dockGroup_dock_dict()
    ...
    dDisplayItem, nested_dynamic_docked_widget_container = self.build_wrapping_nested_dock_area(flat_group_dockitems_list, dock_group_name=dock_group_name)
    ...
```

```453:523:pypho_timeline/docking/dynamic_dock_display_area.py
def build_wrapping_nested_dock_area(self, flat_group_dockitems_list: List[Dock], dock_group_name: str = 'ContinuousDecode_ - t_bin_size: 0.025'):
    ...
    nested_dynamic_docked_widget_container = NestedDockAreaWidget()
    _, dDisplayItem = self.add_display_dock(name, dockSize=dockSize, display_config=display_config, widget=nested_dynamic_docked_widget_container, dockAddLocationOpts=dockAddLocationOpts, autoOrientation=False)
    ...
    for a_dock in flat_group_dockitems_list:
        nested_dynamic_docked_widget_container.displayDockArea.addDock(dock=a_dock)
```

## Revised implementation

1. Add explicit split-group names for timeline docks.
  Use two groups such as `timeline_primary_column` and `timeline_compare_column`.
2. Tag primary track docks as they are created.
  Update `[SpecificDockWidgetManipulatingMixin.add_new_embedded_pyqtgraph_render_plot_widget](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\docking\specific_dock_widget_mixin.py)` or the timeline call sites so the created dock’s `display_config.dock_group_names` includes the primary-column group.
3. Tag compare track docks with the compare-column group.
  When `add_compare_track_view(...)` creates the compare dock, assign the compare-column group instead of only positioning it to the right of the matched row.
4. Rebuild grouped parent containers when splitting.
  After creating compare tracks, call `layout_dockGroups()` on the main dock container so both groups are wrapped into parent docks. If needed, first dissolve old group wrappers with `unwrap_docks_in_all_nested_dock_area()` to avoid stale grouping.
5. Keep independent scrolling behavior unchanged.
  The track sync-group work in `[TrackRenderingMixin](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\rendering\mixins\track_rendering_mixin.py)` still applies; this change is only about dock hierarchy and resizing.

## Files to change

- [c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\widgets\simple_timeline_widget.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\widgets\simple_timeline_widget.py)
- [c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\docking\specific_dock_widget_mixin.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\docking\specific_dock_widget_mixin.py)
- [c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\docking\dynamic_dock_display_area.py](c:\Users\pho\repos\EmotivEpoc\ACTIVE_DEV\pyPhoTimeline\pypho_timeline\docking\dynamic_dock_display_area.py) only if a small helper is needed to re-layout or assign groups cleanly.

## Notes

- This is higher quality than leaving every split track as its own sibling dock, because each column becomes one resizable parent unit.
- It also fits the existing architecture better than inventing a second manual container layer in `SimpleTimelineWidget`.
- The one risk is re-grouping existing docks after they are already shown, so the implementation should use the existing unwrap/re-layout helpers rather than trying to manually reparent docks ad hoc.

