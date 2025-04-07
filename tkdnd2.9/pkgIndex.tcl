package ifneeded tkdnd 2.9 \
  "source \{$dir/tkdnd.tcl\} ; \
   tkdnd::initialise \{$dir\} tkdnd2.9[info sharedlibextension] tkdnd"

package ifneeded tkdnd::utils 2.9 \
  "source \{$dir/tkdnd_utils.tcl\} ; \
   package provide tkdnd::utils 2.9"
