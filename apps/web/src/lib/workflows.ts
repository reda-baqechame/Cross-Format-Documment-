import type { WorkflowPreset } from "@/lib/api";

export interface WorkflowDefinition {
  preset: WorkflowPreset;
  title: string;
  blurb: string;
  audience: string;
  uploadLabel: string;
  revenueSignal: string;
  defaultApprovers: string[];
  defaultRecipients: string[];
}

export const WORKFLOWS: WorkflowDefinition[] = [
  {
    preset: "contract_packet",
    title: "Client contract packet",
    blurb: "Review scope, clauses, reusable fields, approvals, and export proof before sending.",
    audience: "SMB and agency ops",
    uploadLabel: "contract, SOW, proposal, or agreement",
    revenueSignal: "Replaces Acrobat plus manual legal handoffs",
    defaultApprovers: ["Legal Review", "Finance Approval", "Security Review"],
    defaultRecipients: ["counterparty@example.com"],
  },
  {
    preset: "invoice_approval",
    title: "Invoice and deposit review",
    blurb: "Check invoice fields, totals, payment terms, red flags, and approval routing.",
    audience: "SMB finance ops",
    uploadLabel: "invoice, quote, receipt, or statement",
    revenueSignal: "Cuts invoice review and payment delays",
    defaultApprovers: ["AP Review", "Finance Approval"],
    defaultRecipients: ["vendor@example.com"],
  },
  {
    preset: "vendor_onboarding",
    title: "Vendor onboarding",
    blurb: "Turn vendor forms and policies into a repeatable onboarding packet.",
    audience: "Procurement",
    uploadLabel: "vendor packet, W-9, policy, or intake form",
    revenueSignal: "Replaces form builder plus approval routing",
    defaultApprovers: ["Procurement Review", "Security Review"],
    defaultRecipients: ["vendor@example.com"],
  },
  {
    preset: "employee_form_packet",
    title: "Employee form packet",
    blurb: "Prepare intake, consent, checklist, and HR approval fields.",
    audience: "People and HR",
    uploadLabel: "HR packet, consent, checklist, or intake form",
    revenueSignal: "Turns onboarding paperwork into a controlled workflow",
    defaultApprovers: ["HR Review", "People Ops"],
    defaultRecipients: ["employee@example.com"],
  },
  {
    preset: "proposal_to_signature",
    title: "Proposal to signature",
    blurb: "Check SOW details, add signature form fields, route for approval, apply an integrity seal, and validate a sendable copy. (Internal approval + tamper-evident seal - not a legally-binding e-signature.)",
    audience: "Agency sales ops",
    uploadLabel: "proposal, SOW, pitch, or agreement",
    revenueSignal: "Speeds proposal-to-close workflows",
    defaultApprovers: ["Sales Lead", "Legal Review"],
    defaultRecipients: ["buyer@example.com"],
  },
  {
    preset: "bulk_send_template",
    title: "Bulk send from template",
    blurb: "Validate a reusable template and create independent recipient packets.",
    audience: "Ops teams",
    uploadLabel: "template, form, policy, or packet",
    revenueSignal: "Bulk-send workflow for repeatable document ops",
    defaultApprovers: ["Ops Review"],
    defaultRecipients: ["alpha@example.com", "bravo@example.com"],
  },
];

export function getWorkflow(preset: WorkflowPreset): WorkflowDefinition {
  return WORKFLOWS.find((workflow) => workflow.preset === preset) ?? WORKFLOWS[0];
}
