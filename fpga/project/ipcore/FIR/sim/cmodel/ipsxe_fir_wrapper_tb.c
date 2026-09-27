//////////////////////////////////////////////////////////////////////////////
//
// Copyright (c) 2022 PANGO MICROSYSTEMS, INC
// ALL RIGHTS REVERVED.
//
// THE SOURCE CODE CONTAINED HEREIN IS PROPRIETARY TO PANGO MICROSYSTEMS, INC.
// IT SHALL NOT BE REPRODUCED OR DISCLOSED IN WHOLE OR IN PART OR USED BY
// PARTIES WITHOUT WRITTEN AUTHORIZATION FROM THE OWNER.
//
//////////////////////////////////////////////////////////////////////////////
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "ipsxe_fir_def_v1_0.h"

int main() {
    int coef_width = 18;
    int din_width = 25;
    int coef_sum = 16;
    int dout_width = din_width + coef_width + ceil(log2(coef_sum));
    int filter_type = 0;
    int coef_type = 2;
    int round_mode = 0;
    int decim_rate = 2;
    int interp_rate = 3;
    int data_samples = 1024;
    int result;

    double *coef;
    double *din;
    double *dout;

    coef = (double*)malloc(coef_sum*sizeof(double));
    din = (double*)malloc(data_samples*sizeof(double));
    dout = (double*)malloc(data_samples*sizeof(double));

    //long long din_tmp;
    //long long coef_tmp;
    //long long dout_temp;

    //FILE *din_fp;
    //FILE *dout_fp;
    //FILE *coef_fp;
    //din_fp = fopen("./din_exp.txt", "r");
    //coef_fp = fopen("./coef_exp.txt", "r");
    //dout_fp = fopen("./dout.txt", "w");

    int i;
    int j;
    int k;

    //for (i = 0; i < data_samples; i++) {
    //    fscanf(din_fp, "%llx\n", &din_tmp);
    //    din[i] = din_tmp;
    //    //printf("data is %llx\n", din[i]);
    //}

    //for (j = 0; j < coef_sum; j++) {
    //    fscanf(coef_fp, "%llx\n", &coef_tmp);
    //    coef[j] = coef_tmp;
    //}
    for (i = 0; i < data_samples; i++) {
        din[i] = i;
    }
    for (j = 0; j < coef_sum; j++) {
        coef[j] = j;
    }

    result = ipsxe_fir_wrapper_v1_0(coef_sum, coef, coef_width, din, din_width, dout, dout_width, filter_type, coef_type, round_mode, interp_rate, decim_rate, data_samples); 

    //for (k = 0; k < data_samples; k++) {
    //    fprintf(dout_fp, "%lf\n", dout[k]);
    //}
    for (k = 0; k < data_samples; k++) {
        printf("dout[%d] is %lf\n", k, dout[k]);
    }

    //fclose(din_fp);
    //fclose(dout_fp);
    //fclose(coef_fp);
    free(coef);
    free(din);
    free(dout);
}
