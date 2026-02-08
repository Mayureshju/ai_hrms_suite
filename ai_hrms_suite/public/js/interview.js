frappe.ui.form.on("Interview", {
  refresh(frm) {
    frm.add_custom_button("Suggest Slots", () => {
      const interviewers = (frm.doc.interview_details || [])
        .map((row) => row.interviewer)
        .filter(Boolean);

      if (!interviewers.length) {
        frappe.msgprint("Add at least one interviewer to get slot suggestions.");
        return;
      }

      frappe.call({
        method: "ai_hrms_suite.api.hrms.get_interview_slot_suggestions",
        args: {
          job_opening: frm.doc.job_opening,
          interviewers: interviewers,
        },
        freeze: true,
        callback: (res) => {
          const slots = res.message || [];
          if (!slots.length) {
            frappe.msgprint("No available slots found in the configured window.");
            return;
          }

          const options = slots.map((s) => ({ label: s.label, value: s.key }));
          const optionMap = new Map(slots.map((s) => [s.key, s]));

          frappe.prompt(
            [
              {
                fieldname: "slot",
                label: "Suggested Slots",
                fieldtype: "Select",
                options: options.map((o) => o.label).join("\n"),
                reqd: 1,
              },
            ],
            (values) => {
              const selected = options.find((o) => o.label === values.slot);
              if (!selected) {
                return;
              }
              const slot = optionMap.get(selected.value);
              if (!slot) {
                return;
              }
              frm.set_value("scheduled_on", slot.scheduled_on);
              frm.set_value("from_time", slot.from_time);
              frm.set_value("to_time", slot.to_time);
            },
            "Interview Slot Suggestions",
            "Apply Slot"
          );
        },
      });
    });
  },
});
