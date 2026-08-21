RECOMMENDATIONS = {
    # ─── Navigation ─────────────────────────────────────────
    "broken_internal_links": (
        "Fix or remove internal links that point to pages returning 4xx/5xx errors. "
        "Broken links create dead ends that frustrate users and waste crawl budget."
    ),
    "empty_href_links": (
        "Remove anchor tags with empty href attributes. These confuse users and screen "
        "readers and may cause unexpected page jumps."
    ),
    "hash_only_links": (
        "Links pointing to '#hash' only scroll the page. Ensure they have a clear "
        "purpose and that the target section is visible and meaningful."
    ),
    "js_void_links": (
        "Replace 'javascript:void(0)' links with proper <button> elements or real "
        "href URLs. JS-only navigation breaks when JavaScript fails and hurts accessibility."
    ),
    "inaccessible_nav_links": (
        "Some navigation links cannot be reached by keyboard or screen readers. "
        "Ensure all navigation elements use semantic HTML or have proper ARIA roles."
    ),
    "excessive_nav_items": (
        "Navigation has too many items, overwhelming users. Limit top-level navigation "
        "to 5-8 items and use dropdowns or mega-menus for additional pages."
    ),
    "duplicate_nav_links": (
        "Navigation contains duplicate links to the same destination. Remove duplicates "
        "to reduce cognitive load and keep navigation clean."
    ),
    "missing_breadcrumbs": (
        "Add breadcrumb navigation to help users understand their location within the "
        "site hierarchy and navigate back to parent pages."
    ),
    "unclear_anchor_text": (
        "Some links use vague text like 'click here' or 'read more'. Replace with "
        "descriptive text that tells users what they will find on the linked page."
    ),
    "orphan_pages": (
        "Some pages have no incoming internal links, making them undiscoverable. "
        "Add links from relevant pages to improve navigation and SEO."
    ),

    # ─── Interaction ────────────────────────────────────────
    "unlabeled_buttons": (
        "Buttons without text or aria-label are inaccessible to screen readers. "
        "Add visible text, aria-label, or title attributes to all buttons."
    ),
    "tiny_click_targets": (
        "Interactive elements are smaller than 44x44px, making them hard to tap "
        "on mobile. Increase padding or size to meet touch target guidelines."
    ),
    "disabled_visible_buttons": (
        "Buttons appear active but are disabled, confusing users. Either remove them "
        "from view or clearly indicate their disabled state with visual cues."
    ),
    "missing_accessible_names": (
        "Interactive elements lack accessible names for assistive technology. "
        "Add aria-label, aria-labelledby, or visible text to label all interactive elements."
    ),
    "hover_only_functionality": (
        "Content or functionality is only available on hover/mouseover. This excludes "
        "keyboard and touch users. Make the same content available via focus or tap."
    ),
    "horizontal_scroll": (
        "Content causes horizontal scrolling on standard viewports. Use responsive "
        "design, flexible layouts, and overflow handling to prevent horizontal scroll."
    ),
    "hidden_cta": (
        "Primary call-to-action is not immediately visible on page load. Ensure the "
        "main CTA is above the fold and clearly visible without scrolling."
    ),

    # ─── Forms ──────────────────────────────────────────────
    "inputs_without_labels": (
        "Form inputs have no associated <label> element or aria-label. Add labels "
        "to every input so users and screen readers understand what data to enter."
    ),
    "missing_placeholders": (
        "Form inputs lack placeholder text showing expected input format. Add "
        "descriptive placeholders as hints (not replacements for labels)."
    ),
    "incorrect_input_types": (
        "Form inputs use the wrong HTML input type (e.g., type='text' for email). "
        "Use correct types like email, tel, number, date for better mobile keyboards."
    ),
    "required_fields_no_indicator": (
        "Required form fields are not visually marked. Add an asterisk (*) or "
        "'required' label and aria-required='true' to indicate mandatory fields."
    ),
    "no_submit_action": (
        "Form has no submit button or the submit action is not wired up. "
        "Add a clear submit button with proper type='submit'."
    ),
    "submit_no_text": (
        "Submit button has no visible text or aria-label. Add clear text like "
        "'Submit', 'Send', or 'Sign Up' so users know what the button does."
    ),
    "very_long_forms": (
        "Form has too many fields, discouraging completion. Break into multi-step "
        "forms or remove non-essential fields. Only ask for what you truly need."
    ),

    # ─── Mobile ─────────────────────────────────────────────
    "mobile_horizontal_overflow": (
        "Page content overflows horizontally on mobile viewports. Fix by using "
        "max-width, flexible grids, and proper CSS to contain content within the viewport."
    ),
    "mobile_small_text": (
        "Text is too small to read comfortably on mobile. Use a minimum font size "
        "of 16px for body text and ensure sufficient contrast ratios."
    ),
    "mobile_tiny_touch_targets": (
        "Interactive elements are too small for mobile taps. Enlarge clickable areas "
        "to at least 44x44px and add spacing between adjacent targets."
    ),
    "mobile_content_outside_viewport": (
        "Important content is placed outside the visible viewport on mobile. "
        "Ensure all critical content and CTAs are within the initial viewport."
    ),
    "mobile_fixed_element_blocking": (
        "Fixed-position elements (headers, banners, sticky elements) cover important "
        "content on mobile. Reduce their size or add scroll margins for anchored content."
    ),

    # ─── Accessibility ──────────────────────────────────────
    "missing_accessible_names_a11y": (
        "Interactive elements lack accessible names for screen readers. Provide "
        "aria-label, aria-labelledby, or visible text content for all interactive elements."
    ),
    "focusable_no_outline": (
        "Focusable elements have no visible focus indicator. Add :focus-visible styles "
        "so keyboard users can see which element is currently focused."
    ),
    "poor_heading_hierarchy_a11y": (
        "Heading levels skip (e.g., h1 to h3). Maintain a sequential heading hierarchy "
        "so screen reader users can navigate the page structure logically."
    ),
    "missing_skip_nav": (
        "No skip navigation link found. Add a 'Skip to main content' link at the top "
        "of the page so keyboard users can bypass repeated navigation blocks."
    ),
    "landmark_structure_missing": (
        "Page lacks ARIA landmark regions (header, nav, main, footer). Use semantic "
        "HTML5 elements or ARIA roles to define page landmarks for screen readers."
    ),

    # ─── Visual ─────────────────────────────────────────────
    "overlapping_elements": (
        "Elements overlap each other, obscuring content. Fix z-index conflicts, "
        "adjust positioning, and ensure proper spacing between elements."
    ),
    "large_empty_spaces": (
        "Large empty gaps appear between content sections, breaking visual flow. "
        "Review layout and spacing to create a balanced, cohesive page structure."
    ),
    "text_overflow_container": (
        "Text overflows its container, making it unreadable. Use word-wrap, "
        "overflow-wrap, or adjust container width to contain text properly."
    ),
    "images_no_dimensions": (
        "Images lack width and height attributes, causing layout shifts during load. "
        "Add explicit dimensions to prevent cumulative layout shift (CLS)."
    ),
    "inconsistent_button_sizes": (
        "Buttons of the same type have different sizes across pages. Standardize "
        "button dimensions and padding for a consistent, professional appearance."
    ),

    # ─── Readability ────────────────────────────────────────
    "extremely_long_paragraphs": (
        "Paragraphs are too long for comfortable reading. Break text into shorter "
        "paragraphs of 3-5 sentences and use subheadings to organize content."
    ),
    "very_small_text": (
        "Font size is below 14px, reducing readability. Use at least 16px for body "
        "text to ensure comfortable reading on all devices."
    ),
    "excessive_uppercase": (
        "Excessive use of uppercase text reduces readability and feels aggressive. "
        "Reserve uppercase for short labels and headings; use sentence case for body text."
    ),
    "missing_headings": (
        "Page has no headings to structure the content. Add semantic headings (h1-h6) "
        "to organize content and improve both readability and accessibility."
    ),
    "empty_sections": (
        "Page sections contain no meaningful content. Remove empty sections or populate "
        "them with relevant content to avoid confusing users."
    ),
    "placeholder_text": (
        "Page still contains placeholder or lorem ipsum text. Replace all placeholder "
        "content with final copy before publishing."
    ),

    # ─── Performance ────────────────────────────────────────
    "slow_initial_render": (
        "Page has too many blocking resources delaying initial render. Inline critical "
        "CSS, defer non-critical scripts, and optimize resource loading order."
    ),
    "missing_loading_indicators": (
        "No loading indicators for async operations. Add spinners, skeleton screens, "
        "or progress bars so users know content is loading."
    ),
    "large_images": (
        "Some images are excessively large, slowing page load. Compress images, use "
        "modern formats (WebP/AVIF), and serve appropriately sized images per viewport."
    ),

    # ─── Errors ─────────────────────────────────────────────
    "console_errors": (
        "JavaScript errors appear in the browser console. Fix these errors as they "
        "may break functionality and degrade the user experience."
    ),
    "broken_images": (
        "Images fail to load (404 or missing src). Fix or remove broken image "
        "references to avoid showing broken image icons to users."
    ),
    "missing_error_messages": (
        "Form or interactive error states do not display clear error messages. "
        "Show specific, helpful error messages near the relevant field when validation fails."
    ),
    "missing_success_messages": (
        "Completed actions (form submissions, etc.) lack success feedback. "
        "Show confirmation messages so users know their action was processed."
    ),

    # ─── Consistency ────────────────────────────────────────
    "inconsistent_navigation": (
        "Navigation structure differs across pages. Keep navigation consistent "
        "across the entire site so users can always find their way around."
    ),
    "inconsistent_cta_naming": (
        "Similar CTAs use different labels across pages (e.g., 'Sign Up' vs 'Register'). "
        "Standardize CTA text throughout the site for clarity and trust."
    ),
    "inconsistent_footer": (
        "Footer content or layout differs across pages. Maintain a consistent footer "
        "with the same links, contact info, and legal pages on every page."
    ),
    "different_form_styles": (
        "Forms look different across pages, confusing users. Apply consistent styling "
        "to all forms including input fields, buttons, spacing, and validation states."
    ),

    # ─── Trust ──────────────────────────────────────────────
    "missing_contact_info": (
        "No contact information is visible on the page. Add phone number, email, "
        "or physical address to build user trust and provide support channels."
    ),
    "no_cta_detected": (
        "Page has no clear call-to-action. Add a prominent CTA that guides users "
        "toward the desired action (purchase, signup, contact, etc.)."
    ),
    "no_contact_form": (
        "No contact form is available. Add a simple contact form to make it easy "
        "for users to reach out with questions or support requests."
    ),
    "missing_privacy_links": (
        "No privacy policy or terms of service links found. Add links to legal pages "
        "in the footer to comply with regulations and build user trust."
    ),
    "missing_social_proof": (
        "No social proof elements (testimonials, reviews, trust badges) are present. "
        "Add social proof to build credibility and increase conversion rates."
    ),
}
