/**
 * Data-integrity checks for the shared projects source (lib/projects.ts).
 *
 * Fails if any project is missing a field the footer (and carousel) rely on:
 *   - `name`   -> the footer Work column display title
 *   - `slug`   -> the footer link href (/?work=<slug>#work)
 *   - `image` / `alt` / `category` / `note` -> carousel + lightbox rendering
 *
 * Run with: npm run test:data   (node --test, using Node's built-in TS stripping)
 */
import assert from "node:assert/strict";
import { describe, test } from "node:test";

import { projects, type Project } from "../lib/projects.ts";

const REQUIRED_STRING_FIELDS: (keyof Project)[] = [
  "slug",
  "category",
  "name",
  "image",
  "alt",
  "note",
];

const footerHref = (project: Project) => `/?work=${project.slug}#work`;

describe("shared projects data", () => {
  test("exports a non-empty array", () => {
    assert.ok(Array.isArray(projects));
    assert.ok(projects.length > 0);
  });

  projects.forEach((project, index) => {
    test(`project ${index} has every required field`, () => {
      for (const field of REQUIRED_STRING_FIELDS) {
        const value = project[field];
        if (typeof value !== "string" || value.trim() === "") {
          throw new Error(
            `projects[${index}] (${project.slug ?? "unknown"}) is missing required field "${field}"`,
          );
        }
      }
    });
  });

  test("slugs are url-safe and unique", () => {
    const seen = new Set<string>();
    for (const project of projects) {
      assert.match(project.slug, /^[a-z0-9]+(?:-[a-z0-9]+)*$/);
      assert.equal(seen.has(project.slug), false);
      seen.add(project.slug);
    }
  });

  test("display titles are unique and human readable", () => {
    const names = projects.map((project) => project.name);
    assert.equal(new Set(names).size, names.length);
    for (const name of names) {
      assert.equal(name.trim(), name);
      assert.ok(name.length > 2);
    }
  });

  test("footer lightbox links resolve to a deep link per project", () => {
    for (const project of projects) {
      const href = footerHref(project);
      assert.equal(href, `/?work=${project.slug}#work`);
      const url = new URL(href, "https://example.com");
      assert.equal(url.searchParams.get("work"), project.slug);
      assert.equal(url.hash, "#work");
    }
  });

  test("images resolve to a usable src and have descriptive alt text", () => {
    for (const project of projects) {
      assert.match(project.image, /^(https?:\/\/|\/|data:)/);
      assert.ok(project.alt.split(/\s+/).length >= 3);
    }
  });
});
