//! AWS S3 multipart-upload helper types.
//!
//! Included for completeness and future use; the current blob pipeline uses
//! a single `PutObject` call (Option-B in-memory buffering) rather than
//! streaming multipart upload.

use aws_sdk_s3::types::{CompletedMultipartUpload, CompletedPart};

/// Carries the information needed to finalise one multipart part.
pub struct PartInfo {
    pub part_number: i32,
    pub etag: String,
}

/// Assemble a `CompletedMultipartUpload` value from a slice of `PartInfo`.
pub fn build_completed_multipart(parts: &[PartInfo]) -> CompletedMultipartUpload {
    let mut completed_parts: Vec<CompletedPart> = Vec::with_capacity(parts.len());
    for p in parts {
        let part = CompletedPart::builder()
            .part_number(p.part_number)
            .e_tag(p.etag.clone())
            .build();
        completed_parts.push(part);
    }
    CompletedMultipartUpload::builder()
        .set_parts(Some(completed_parts))
        .build()
}
