package com.example.wooddetect.common;

public final class DetectionStatus {
    public static final String PENDING = "PENDING";
    public static final String PROCESSING = "PROCESSING";
    public static final String SUCCESS = "SUCCESS";
    public static final String FAIL = "FAIL";

    public static final String BATCH_PENDING = "PENDING";
    public static final String BATCH_PROCESSING = "PROCESSING";
    public static final String BATCH_SUCCESS = "SUCCESS";
    public static final String BATCH_PARTIAL_FAIL = "PARTIAL_FAIL";
    public static final String BATCH_FAIL = "FAIL";

    private DetectionStatus() {
    }
}
