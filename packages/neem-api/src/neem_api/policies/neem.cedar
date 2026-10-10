// Who may do what in Neem. Evaluated by Cedar on every request that costs compute or changes
// a school's record. Reads stay open: the heat of a schoolyard is public information.

// Anyone may look at a school's heat twin and try designs in the browser.
permit (
  principal,
  action in [Neem::Action::"ViewTwin", Neem::Action::"PreviewDesign"],
  resource is Neem::School
);

// Anyone may ask for physics verification, within a size and rate budget: each run costs
// several seconds of GPU locally, or about a minute of Lambda.
permit (
  principal,
  action == Neem::Action::"VerifyDesign",
  resource is Neem::School
)
when {
  context.trees <= 200 &&
  context.sails <= 40 &&
  context.recent_jobs < 20
};

// A school's own planner may approve a plan for that school, and no other.
permit (
  principal in Neem::Role::"planner",
  action == Neem::Action::"ApproveDesign",
  resource is Neem::School
)
when { principal.schools.contains(resource) };

// City administrators may do everything, including rerunning the city-wide ranking.
permit (
  principal in Neem::Role::"admin",
  action,
  resource
);

// Nobody approves a plan that physics has not verified, whoever they are.
forbid (
  principal,
  action == Neem::Action::"ApproveDesign",
  resource
)
unless { context.verified };
